import json
from decimal import Decimal
from datetime import date, timedelta
from django.urls import reverse

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
from wallet.utils import get_or_create_wallet, debit_wallet

from coupons.utils import record_coupon_usage
from coupons.models import Coupon


import logging
logger = logging.getLogger('project_logger')


# Create your views here.

@login_required(login_url='login')
def create_razorpay_order(request):
    """
    Prepare totals and create Razorpay order (no DB Order yet).
    Uses the same business rules as place_order (buy_now / cart).
    applies wallet first, then Razorpay for remaining.
    """

    if request.method != "GET":
        return JsonResponse({"status":"error", "message":"Invalid request method."}, status=405)
    
    user = request.user

    # NEW FIX: Store selected address in session for Razorpay verify
    selected_address_id = request.GET.get("address_id")
    if selected_address_id:
        request.session["selected_address_id"] = selected_address_id
        request.session.modified = True



    #Must have a selected address to create order
    if not selected_address_id:
        return JsonResponse({"status":"error", "message":"Please select a delivery address."}, status=400)
    
    shipping_address = get_object_or_404(Address, id=selected_address_id, user=user)
    buy_now_item = request.session.get('buy_now')

    # default values for wallet usage
    wallet_used = Decimal('0.00')
    online_amount = Decimal('0.00')
    use_wallet = request.session.get('use_wallet', False)
    wallet = get_or_create_wallet(user)

    #get coupon discount from session or 0.00
    coupon_discount = Decimal(request.session.get('coupon_discount', '0.00'))

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

        total_amount = subtotal - coupon_discount + shipping_charge

        if use_wallet and wallet.balance > 0:
            wallet_used = min(wallet.balance, total_amount)
            online_amount = total_amount - wallet_used
        else:
            online_amount = total_amount

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

        total_amount = subtotal - coupon_discount + shipping_charge


        wallet_used = Decimal('0.00')
        online_amount = total_amount  #what razorpay will charge

        if use_wallet and wallet.balance > 0:
            wallet_used = min(wallet.balance, total_amount)
            online_amount = total_amount - wallet_used
        
        #if wallet covers full amount , don't razorpay
        if online_amount <= 0:
            request.session['wallet_only_checkout'] = True
            return JsonResponse({"status": "wallet_only", "redirect_url": reverse("place_order")})

    amount_paise = int(online_amount * 100) # Convert to paise

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

        "wallet_used": str(wallet_used),
        "online_amount": str(online_amount),
        "use_wallet": bool(use_wallet),
        "coupon_discount": str(coupon_discount)
    }

    request.session.modified = True

    # print("DEBUG: address_id from JS =", request.GET.get("address_id"))
    # print("SESSION selected_address_id =", request.session.get("selected_address_id"))
    # print("ALL SESSION KEYS NOW:", dict(request.session))




    return JsonResponse({
        "status": "success",
        "order_id": razorpay_order['id'],
        "amount": amount_paise,
        "key": settings.RAZORPAY_KEY_ID,
        "name": "Timestamp Store",
        "description": "Watch Purchase"

    })

@csrf_exempt
@transaction.atomic
def verify_payment(request):
    """
    Verify Razorpay payment, then create Order + OrderItems
    mirroring the logic from place_order but with ONLINE payment.
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method."}, status=405)
    
    try:
        data = json.loads(request.body)   #request.body → raw request data (bytes) from the JS fetch POST.    json.loads(...) → converts it into a Python dictionary data.
        logger.debug(f"PAYMENT RESPONSE RAW: {data}")

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
    logger.debug(f"PENDING SESSION DATA: {pending}")

    if not pending or pending.get('razorpay_order_id') != razorpay_order_id:
        return JsonResponse({"status":"error","message":"No matching pending payment found."}, status=400)

    logger.debug("VERIFY FLOW CONTINUES: passed session check")

    # print("DEBUG: mode =", pending.get("mode"))
    # print("DEBUG: selected_address_id from session =", request.session.get("selected_address_id"))
    # print("DEBUG: subtotal =", pending.get("subtotal"))
    # print("DEBUG: discount_amount =", pending.get("discount_amount"))
    # print("DEBUG: shipping_charge =", pending.get("shipping_charge"))
    # print("DEBUG: total_amount =", pending.get("total_amount"))
    # print("DEBUG: wallet_used =", pending.get("wallet_used"))
    # print("DEBUG: online_amount =", pending.get("online_amount"))
    # print("DEBUG: Going to fetch address now...")


    user = request.user
    mode = pending.get('mode') # buy_now / cart

    #Address again (in case changed)
    selected_address_id = request.session.get('selected_address_id')
    if not selected_address_id:
        return JsonResponse({"status":"error", "message":"Please select a delivery address."}, status=400)

    shipping_address = get_object_or_404(Address, id=selected_address_id, user=user)

    subtotal = Decimal(pending['subtotal'])
    discount_amount = Decimal(pending['discount_amount'])
    shipping_charge = Decimal(pending['shipping_charge'])
    total_amount = Decimal(pending['total_amount'])

    wallet_used = Decimal(pending.get('wallet_used', '0.00'))
    online_amount = Decimal(str(pending.get('online_amount', total_amount)))

    coupon_discount = Decimal(pending.get('coupon_discount', '0.00'))

    # We must check that Razorpay amount == online_amount
    try:
        rp_order = razorpay_client.order.fetch(razorpay_order_id)
        rp_amount = Decimal(rp_order['amount'] / 100).quantize(Decimal('0.01')) # convert paise to INR  and prevent floating by quantize
    except:
        return JsonResponse({"status": "error", "message": "Failed to verify Razorpay order amount."}, status=400)   
    
    if rp_amount != online_amount:
        logger.error(f"Amount mismatch! Expected {online_amount}, got {rp_amount}")
        return JsonResponse({"status": "error", "message": "Payment amount mismatch."}, status=400)




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
            return JsonResponse(
                {"status":"error", "message":"Product not available or out of stock."},
                status=400
            )

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
            original_price = cart_item.variant.price
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
            cart_item.variant.stock -= cart_item.quantity
            cart_item.variant.save()

        #Clear cart
        cart.items.all().delete()
        cart.total = Decimal('0.00')
        cart.save()
    
    #wallet debit (after order created)
    if wallet_used > 0:
        success, msg = debit_wallet(
            user=user,
            amount=wallet_used,
            tx_type='debit',
            description=f"Wallet used for order {order.order_id}",
            order=order
        )
        #if somehow fails
        if not success:
            logger.error(f"Wallet debit failed for user {user.id}: {msg}")
            raise Exception("Wallet debit failed")
        
    #record coupon usage
    if  'applied_coupon_id' in request.session:
        try:
            coupon = Coupon.objects.get(id=request.session['applied_coupon_id'])
            discount = Decimal(request.session['coupon_discount'])
            cart_total_before = Decimal(request.session['cart_total_before_coupon'])

            record_coupon_usage(
                coupon=coupon,
                user=user,
                order=order,
                discount_amount=discount,
                cart_total_before_discount=cart_total_before
            )

            del request.session['applied_coupon_id']
            del request.session['coupon_discount']
            del request.session['cart_total_before_coupon']
        except Exception as e:
            logger.error(f"Coupon recording error: {e}")



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

    if 'pending_payment' in request.session:
        del request.session['pending_payment']

    #for existing order_success view
    request.session['last_order_id'] = order.id
        
    return JsonResponse({"status": "success"})


