import json
from decimal import Decimal
from datetime import date, timedelta

from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from .utils import razorpay_client
from orders.models import Order
from accounts.models import Address
from products.models import Product_varients
from cart.utils import get_or_create_cart, validate_cart_for_checkout
from orders.models import Order, OrderItem, OrderStatusHistory

# Create your views here.

def create_razorpay_order(request):
    """
    Prepare totals and create Razorpay order (no DB Order yet).
    Uses the same business rules as place_order (buy_now / cart).
    """

    if request.method != "GET":
        return JsonResponse({"status":"error", "message":"Invalid request method."}, status=405)
    
    user = request.user
    #Must have a selected address to create order
    selected_address_id = request.session.get('selected_address_id')
    if not selected_address_id:
        return JsonResponse({"status":"error", "message":"Please select a delivery address."}, status=400)
    
    shipping_address = get_object_or_404(Address, id=selected_address_id, user=user)
    buy_now_item = request.session.get('buy_now')

    #buy now flow
    if buy_now_item:
        try:
            variant = Product_varients.objects.select_related('product').get(id=buy_now_item['variant_id'])
            product = variant.product
        except Product_varients.DoesNotExist:
            return JsonResponse({"status":"error", "message":"Product not found."}, status=400)
        
        quantity = buy_now_item.get('quantity', 1)
        # Handle both cases: price in session or not
        price = Decimal(str(buy_now_item.get('price', variant.price)))

        if not product.is_listed or not variant.is_listed:
            return JsonResponse({"status":"error", "message":"Product is not available."}, status=400)
        
        if variant.stock < quantity:
            return JsonResponse({"status":"error", "meesage":"Not enough stock available."}, status=400)
        
        subtotal = price * quantity
        discount_amount = Decimal('0.00') # Implement any discount logic if needed
        shipping_charge = Decimal('0.00') if subtotal >= 2000 else Decimal('50.00')
        total_amount = subtotal - discount_amount + shipping_charge

    else:
        #cart flow
        cart = get_or_create_cart(user)
        #same validation as place_order
        is_valid, errors = validate_cart_for_checkout(cart)
        if not is_valid:
            return JsonResponse({"status":"error", "message": errors[0] if errors else "Cart is not valid for checkout."}, status=400)
        
        cart_items = cart.items.select_related('product', 'variant')
        subtotal = cart.total

        #listing and stock check
        for item in cart_items:
            if not item.product.is_listed or not item.variant.is_listed:
                return JsonResponse({"status":"error", "message":f"{item.product.product_name} is unavailable."}, status=400)
            if item.variant.stock < item.quantity:
                return JsonResponse({"status":"error", "message":f"Not enough stock for {item.product.product_name}."}, status=400)
            
        discount_amount = Decimal('0.00') # Implement any discount logic if needed
        shipping_charge = Decimal('0.00') if subtotal >= 2000 else Decimal('50.00')
        total_amount = subtotal - discount_amount + shipping_charge


    amount_paise = int(total_amount * 100) # Convert to paise

    data = {
        'amount': amount_paise,
        'currency': 'INR',
        'receipt': f'TS_{user.id}_{timezone.now().strftime("%Y%m%d%H%M%S")}',
        'payment_capture': 1   #1 = true / auto-capture the payment as soon as user pays
    }

    razorpay_order = razorpay_client.order.create(data)

    # Save info in session so verify_payment can create DB Order correctly
    request.session['pending_payment'] = {
        "mode": "buy_now" if buy_now_item else "cart",
        "razorpay_order_id": razorpay_order['id'],
        "subtotal": str(subtotal),
        "discount_amount": str(discount_amount),
        "shipping_charge": str(shipping_charge),
        "total_amount": str(total_amount),
    }

    request.session.modified = True

    return JsonResponse({
        "status": "success",
        "order_id": razorpay_order['id'],
        "amount": amount_paise,
        "key": settings.RAZORPAY_KEY_ID,
        "name": "Timestamp Store",
        "description": "Watch Purchase"

    })

@csrf_exempt
@login_required(login_url='login')
@transaction.atomic
def verify_payment(request):
    """
    Verify Razorpay payment, then create Order + OrderItems
    mirroring the logic from place_order but with ONLINE payment.
    """
    if request.method != "POST":
        return JsonResponse
    
    try:
        data = json.loads(request.body)   #request.body → raw request data (bytes) from the JS fetch POST.    json.loads(...) → converts it into a Python dictionary data.
    except json.JSONDecodeError:
        print("Invalid JSON received in verify_payment.")
        return JsonResponse({"status": "error", "message": "Invalid JSON."}, status=400)

    razorpay_order_id = data.get('razorpay_order_id')  #Extracts the values from the data dictionary.   .get("key") returns the value or None if key not present.
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_signature = data.get('razorpay_signature')

    if not (razorpay_order_id and razorpay_payment_id and razorpay_signature):
        return JsonResponse({"status":"error","message":"Missing payment details."}, status=400)

    #Verify signature from Razorpay
    params = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }

    try:
        razorpay_client.utility.verify_payment_signature(params)
    except:
        return JsonResponse({'status': 'failure', 'message': 'Payment verification failed.'}, status=400)
    
    pending = request.session.get('pending_payment')
    if not pending or pending.get('razorpay_order_id') != razorpay_order_id:
        return JsonResponse({"status":"error","message":"No matching pending payment found."}, status=400)

    mode = pending.get('mode') # buy_now / cart

    user = request.user

    #Address again (in case changed)
    selected_address_id = request.session.get('selected_address_id')
    if not selected_address_id:
        return JsonResponse({"status":"error", "message":"Please select a delivery address."}, status=400)

    shipping_address = get_object_or_404(Address, id=selected_address_id, user=user)

    subtotal = Decimal(pending['subtotal'])
    discount_amount = Decimal(pending['discount_amount'])
    shipping_charge = Decimal(pending['shipping_charge'])
    total_amount = Decimal(pending['total_amount'])

    # create order 
    order = Order.objects.create(
        user=user,
        shipping_address=shipping_address,
        full_name=shipping_address.full_name,
        mobile=shipping_address.mobile,
        street_address=shipping_address.street_address,
        city=shipping_address.city,
        state=shipping_address.state,
        postal_code=shipping_address.postal_code,
        subtotal=subtotal,
        discount_amount=discount_amount,
        shipping_charge=shipping_charge,
        total_amount=total_amount,
        payment_method='online',
        payment_status='completed',
        status='pending',
        order_notes='',
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature,

    )
    order.estimated_delivery = date.today() + timedelta(days=7)
    order.save()

    #create order items and reduce stock
    if mode == 'buy_now':
        buy_now_item = request.session.get('buy_now')
        if not buy_now_item:
            return JsonResponse({"status":"error","message":"Buy now session expired."}, status=400)
        
        try:
            variant = Product_varients.objects.select_related('product').get(id=buy_now_item['variant_id'])
            product = variant.product
        except Product_varients.DoesNotExist:
            return JsonResponse({"status":"error", "message":"product variant not found."},status=400)
        
        quantity = buy_now_item.get('quantity', 1)
        price = Decimal(str(buy_now_item.get('price', variant.price)))

        if not product.is_listed or not variant.is_listed or variant.stock < quantity:
            return JsonResponse({"status":"error", "message":"Product not available or out of stock."}, status)

        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.product_name,
            variant=variant,
            variant_colour=variant.colour,
            price=price,
            original_price=variant.price,
            discount_amount=Decimal('0.00'),
            quantity=quantity,
            status='pending',

        )
        #reduce stock
        variant.stock -= quantity
        variant.save()

    else:
        #cart flow
        cart = get_or_create_cart(user)
        cart_items = cart.items.select_related('product', 'variant').all()

        # Re-check listing and stock
        for item in cart_items:
            if not item.product.is_listed or not item.variant.is_listed:
                return JsonResponse({"status":"error", "message":f"{item.product.product_name} is unavailable or out of stock."}, status=400)
            
            if  item.variant.stock <= 0 or item.variant.stock < item.quantity:
                return JsonResponse({"status":"error", "message":f"Not enough stock for {item.product.product_name}."}, status=400)
        
        for cart_item in cart_items:
            original_price = cart_items.variant.price
            item_discount = Decimal('0.00') 

            # if cart_item.product.offer and cart_item.product.offer.is_active:
            #     item_discount = (cart_item.variant.price - original_price) * cart_item.quantity

            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                variant=cart_item.variant,
                product_name=cart_item.product.product_name,
                variant_colour=cart_item.variant.colour,
                price=cart_item.price,
                original_price=original_price,
                discount_amount=item_discount,
                quantity=cart_item.quantity,
                status='pending',
            )

            #Reduce stock
            cart_item.variant.stock -= cart_items.quantity
            cart_item.variant.save()

        #Clear cart
        cart.items.all().delete()
        cart.total = Decimal('0.00')
        cart.save()

    # status history
    OrderStatusHistory.objects.create(
        order=order,
        old_status='',
        new_status='pending',
        changed_by=user,
        notes='Order placed sucessfully via online payment.'
    )

    #clean up sessions
    if mode == 'buy_now' and 'buy_now' in request.session:
        del request.session['buy_now']
    
    if 'selected_address_id' in request.session:
        del request.session['selected_address_id']

    #for existing order_success view
    request.session['last_order_id'] = order.id
        
    return JsonResponse({"status": "success"})


