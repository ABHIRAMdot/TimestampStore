import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse
from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


from .models import Order, OrderItem, OrderStatusHistory
from .forms import CancelOrderForm, CancelOrderItemForm, ReturnOrderItemForm
from .utils import cancel_order, search_orders, check_and_update_order_status_after_item_change
from .invoice import generate_invoice_pdf
from accounts.models import Address
from products.models import Product, Product_varients
from  offers.utils import apply_offer_to_variant
from wallet.models import Wallet
from cart.utils import get_or_create_cart, validate_cart_for_checkout
from coupons.utils import validate_and_apply_coupon, record_coupon_usage
from coupons.models import Coupon



@login_required(login_url='login')
def user_orders_list(request):
    """Display list of user's orders"""
    
    search_query = request.GET.get('search', '').strip()
    
    orders = Order.objects.filter(user=request.user).select_related('user', 'shipping_address').prefetch_related('items__product', 'items__variant')
    
    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query) |
            Q(items__product_name__icontains=search_query)
        ).distinct()
    
    paginator = Paginator(orders, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    breadcrumbs = [
    {"label": "Home", "url": reverse("home")},
    {"label": "Cart", "url": reverse("cart_view")},
    {"label": "My orders", "url": None},
    ]
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'breadcrumbs':breadcrumbs
    }
    
    return render(request, 'orders/user_orders_list.html', context)


@login_required(login_url='login')
def user_order_detail(request, order_id):
    """Display detailed view of a specific order"""
    
    order = get_object_or_404(
        Order.objects.select_related('user', 'shipping_address'),
        order_id=order_id,
        user=request.user
    )
    
    context = {'order': order}
    return render(request, 'orders/user_order_detail.html', context)


@login_required(login_url='login')
def cancel_order_view(request, order_id):
    """Cancel entire order"""
    
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    
    if not order.can_be_cancelled:
        messages.error(request, "This order cannot be cancelled.")
        return redirect('user_order_detail', order_id=order.order_id)
    
    if request.method == 'POST':
        form = CancelOrderForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data.get('reason', '').strip() or "No reason provided"
            success, message = cancel_order(order, reason=reason, cancelled_by=request.user)
            
            if success:
                messages.success(request, message)
                return redirect('user_order_detail', order_id=order.order_id)
            else:
                messages.error(request, message)
    else:
        form = CancelOrderForm()
    
    context = {'order': order, 'form': form}
    return render(request, 'orders/cancel_order.html', context)


@login_required(login_url='login')
def cancel_order_item_view(request, item_id):
    """Cancel individual order item"""
    
    item = get_object_or_404(
        OrderItem.objects.select_related('order', 'product', 'variant'),
        id=item_id,
        order__user=request.user
    )
    
    if not item.can_be_cancelled:
        messages.error(request, "This item cannot be cancelled.")
        return redirect('user_order_detail', order_id=item.order.order_id)
    
    if request.method == 'POST':
        form = CancelOrderItemForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data.get('reason', '').strip() or "No reason provided"
            success, message = item.cancel_item(reason=reason, cancelled_by=request.user)
            
            if success:
                # Check and update order status if all items are cancelled
                check_and_update_order_status_after_item_change(item.order)
                messages.success(request, message)
            else:
                messages.error(request, message)
            
            return redirect('user_order_detail', order_id=item.order.order_id)
    else:
        form = CancelOrderItemForm()
    
    context = {'item': item, 'form': form}
    return render(request, 'orders/cancel_order_item.html', context)


@login_required(login_url='login')
def return_order_item_view(request, item_id):
    """Request return for order item"""
    
    item = get_object_or_404(
        OrderItem.objects.select_related('order', 'product', 'variant'),
        id=item_id,
        order__user=request.user
    )
    
    if not item.can_be_returned:
        messages.error(request, "This item cannot be returned. Either it's not delivered yet or the 7-day return window has expired.")
        return redirect('user_order_detail', order_id=item.order.order_id)

    #Check if already returned or return requested
    if  item.status in['return_requested', 'returned']:
        messages.warning(request, "Returned request already submitted for this item.")
        return redirect('user_order_details', order_id=item.order.order_id)
    
    if request.method == 'POST':
        form = ReturnOrderItemForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            success, message = item.request_return(reason=reason)
            
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)
            
            return redirect('user_order_detail', order_id=item.order.order_id)
    else:
        form = ReturnOrderItemForm()
    
    context = {'item': item, 'form': form, 'order': item.order}
    return render(request, 'orders/return_order_item.html', context)


@login_required(login_url='login')
def download_invoice(request, order_id):
    """Download PDF invoice for order"""
    
    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        order_id=order_id,
        user=request.user
    )
    
    return generate_invoice_pdf(order)


@login_required(login_url='login')
def buy_now(request):
    """Store seelcted item n sesion and redirect to checkout"""    

    if request.method != 'POST':
        return redirect('home')
    
    product_id = request.POST.get('product_id')
    variant_id = request.POST.get('variant_id')
    slug = request.POST.get('slug')
    quantity = int(request.POST.get('quantity', 1))

    if not product_id or not variant_id:
        messages.error(request, "Invalid item selection")
        return redirect('home')

    #fetch varianr to get correct price
    try:
        variant = Product_varients.objects.select_related('product').get(id=variant_id)
    except Product_varients.DoesNotExist:
        messages.error(request, "product variant not found.")
        return redirect('home')
    
    if not variant.product.is_listed:
        return render(request, "error/product_unavailable.html", status=404)
    
    pricing = apply_offer_to_variant(variant)

    
    #save butnow items into session
    request.session['buy_now'] = {
        "product_id":int(product_id),
        "variant_id": int(variant_id),
        'slug': slug,
        "quantity": quantity,

        #store final price
        'price': float(pricing['final_price']),
        "original_price": float(pricing['original_price']),
        "discount_amount": float(pricing['discount_amount']),
        "discount_percentage": str(pricing['discount_percentage']),
        "has_offer": bool(pricing['has_offer']),
    }

    return redirect('checkout')


# CHECKOUT VIEWS
@login_required(login_url='login')
def checkout_view(request):
    """Display checkout page with addresses and order summery"""

    if request.method == 'POST' and 'from_cart_checkout' in request.POST:
        request.session.pop('buy_now', None)


    discount_from_coupon = Decimal('0.00')
    applied_coupon = None

    if request.method == 'POST':
        #user clicked apply coupon
        if 'apply_coupon' in request.POST:
            coupon_code = request.POST.get('coupon_code', '').strip()

            #calculate cart total before coupon
            buy_now_item = request.session.get('buy_now')
            if buy_now_item:
                # for buy now
                cart_total = Decimal(str(buy_now_item['price'])) * buy_now_item['quantity']
            else:
                #for cart
                cart = get_or_create_cart(request.user)
                cart_total = cart.total
            
            #validate and apply coupon
            success, message, discount, coupon  = validate_and_apply_coupon(
                coupon_code, request.user, cart_total
            )

            if success:
                request.session['applied_coupon_id'] = coupon.id
                request.session['coupon_discount'] = str(discount)
                request.session['cart_total_before_coupon'] = str(cart_total)
                messages.success(request, message)
                discount_from_coupon = discount
                applied_coupon = coupon
            else:
                messages.error(request, message)
                
        
        #use clicked remove coupon
        elif 'remove_coupon' in request.POST:
            if'applied_coupon_id' in request.session:
                del request.session['applied_coupon_id']
                del request.session['coupon_discount']
                del request.session['cart_total_before_coupon']
                messages.info(request, "Coupon removed")

    #Get coupon from session if exists (When page loads normally)
    elif 'applied_coupon_id' in request.session:
        try:
            applied_coupon = Coupon.objects.get(id=request.session['applied_coupon_id'])
            discount_from_coupon = Decimal(request.session['coupon_discount'])

        except Coupon.DoesNotExist:
            #coupon was deleted, clean session
            del request.session['applied_coupon_id']
            del request.session['coupon_discount']
            if 'cart_total_before_coupon' in request.session:
                del request.session['cart_total_before_coupon']



    if  request.method == 'POST' and request.POST.get('buy_now_product_id'):
        product_id = int(request.POST['buy_now_product_id'])
        variant_id = int(request.POST['buy_now_variant_id'])
        quantity = int(request.POST['buy_now_qty'])
        slug = request.POST['buy_now_slug']

        try:
            product = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            # Product completely missing
            return render(request, "errors/product_unavailable.html", status=404)
    
        #Block unlisted product even user came erlier
        if not product.is_listed:
            return render(request, "errors/product_unavailable.html", status=404)
    

        variant = Product_varients.objects.select_related('product').get(id=variant_id)
        product = variant.product

        pricing = apply_offer_to_variant(variant)

        # store buynow items in session
        request.session['buy_now'] = {
            'product_id': product_id,
            'variant_id': variant_id,
            'quantity': quantity,

            'price': float(pricing['final_price']),       # final price after offer
            'original_price': float(pricing['original_price']),
            'discount_amount': float(pricing['discount_amount']),
            'discount_percentage': str(pricing['discount_percentage']),
            'has_offer': bool(pricing['has_offer']),
        }
        
        return redirect('checkout')
    
    buy_now_item = request.session.get('buy_now')
    if buy_now_item:
        variant = Product_varients.objects.select_related('product').get(id=buy_now_item['variant_id']) 
        product = variant.product
        quantity = int(buy_now_item['quantity'])
        price = Decimal(str(buy_now_item['price'])) 
        original_price = Decimal(str(buy_now_item.get('original_price', price)))
        item_discount = Decimal(str(buy_now_item.get('discount_amount', 0)))

        #temp cart_items to list in the template loop
        cart_items = [{
            'product': product,
            'variant': variant,
            'product_name': product.product_name,
            'variant_colour': variant.colour,
            'quantity': quantity,
            'price': price,
            'original_price': original_price,
            'discount_amount': item_discount,
            'total': price * quantity,
        }]

        mrp_total = original_price * quantity
        subtotal = price * quantity
        discount_amount = item_discount * quantity

    else:

        cart = get_or_create_cart(request.user)

        #validate cart
        is_valid, errors = validate_cart_for_checkout(cart)
        if not is_valid:
            for error in errors:
                messages.error(request, error)
            return redirect('cart_view')

        #Calculate total summary
        cart_items_qs = cart.items.select_related('product', 'variant').all()
        cart_items = []

        mrp_total = Decimal('0.00')
        subtotal = Decimal('0.00')
        discount_amount = Decimal('0.00')


        for item in cart_items_qs:
            # Recompute pricing from offers utils for display (do not change cart DB)
            pricing = apply_offer_to_variant(item.variant)
            final_price = Decimal(str(pricing['final_price']))
            original_price = Decimal(str(pricing['original_price']))
            item_discount = Decimal(str(pricing['discount_amount']))

            line_total = final_price * item.quantity

            cart_items.append({
                'product': item.product,
                'variant': item.variant,
                'product_name': item.product.product_name,
                'variant_colour': item.variant.colour,
                'quantity': item.quantity,
                'price': final_price,
                'original_price': original_price,
                'discount_amount': item_discount,  # per single item
                'total': line_total,
                'has_offer': pricing['has_offer'],
                'offer_name': pricing.get('offer_name'),
                'discount_percentage': pricing.get('discount_percentage'),
            })
            mrp_total += original_price * item.quantity
            subtotal += line_total
            discount_amount += (item_discount * item.quantity)


    
    #Get user addresses
    addresses = Address.objects.filter(user=request.user).order_by('-created_at')


    #Get selected address from session
    selected_address_id = request.session.get('selected_address_id')
    selected_address = None

    if selected_address_id:
        selected_address = addresses.filter(id=selected_address_id).first()

    if not selected_address and addresses.exists():
        selected_address = addresses.first()
        request.session['selected_address_id'] = selected_address.id 




    # Tax calculation (18% GST example)
    tax_rate = Decimal('0.18')
    # tax_amount = (subtotal - discount_amount) * tax_rate

    #Shipping free above 1000
    shipping_charge = Decimal('0.00') if subtotal >= 1000 else Decimal('50.00')

    # original_price = original_price * quantity

    # Total amount
    total_amount = subtotal - discount_from_coupon + shipping_charge  # + tax_amount

    #using wallet amount
    use_wallet = request.session.get("use_wallet", False)
    wallet, created = Wallet.objects.get_or_create(user=request.user)    

    wallet_used = Decimal('0.00')

    if use_wallet and wallet.balance > 0:
        wallet_used = min(wallet.balance, total_amount)
    
    remaining_amount = total_amount - wallet_used

    remaining_amount = remaining_amount.quantize(Decimal("0.01"))
    wallet_used = wallet_used.quantize(Decimal("0.01"))
    
    total_amount = total_amount.quantize(Decimal('0.01'))



    
    breadcrumbs = [
        {"label": "Home", "url": reverse("home")},
        {"label": "Cart", "url": reverse("cart_view")},
        {"label": "Checkout", "url": None},
    ]
    estimated_delivery = date.today() + timedelta(days=7)

    context = {
        'addresses': addresses,
        'selected_address': selected_address,
        'cart_items': cart_items,
        'subtotal': subtotal,
        # 'tax_amount': tax_amount,
        # 'tax_rate': tax_rate * 100,
        'discount_amount': discount_amount,
        'shipping_charge': shipping_charge,
        'total_amount': total_amount,
        'estimated_delivery': estimated_delivery,
        'breadcrumbs': breadcrumbs,

        'mrp_total': mrp_total.quantize(Decimal('0.01')),

        'wallet':wallet,
        'use_wallet': use_wallet,
        'wallet_used': wallet_used,
        'remaining_amount': remaining_amount,

        'applied_coupon': applied_coupon,
        'coupon_discount': discount_from_coupon,

    }    

    return render(request, 'orders/checkout.html', context)


@login_required(login_url='login')
def select_address(request, address_id):
    """Select delivery address"""
    address = get_object_or_404(Address, id=address_id, user=request.user)
    request.session['selected_address_id'] = address.id 
    messages.success(request, "Delivery address selected.")
    return redirect('checkout')


@login_required(login_url='login')
@transaction.atomic
def place_order(request):
    """Place order with COD"""
    if request.method != 'POST':
        return redirect('checkout')
    
    #buy now place order
    buy_now_item = request.session.get('buy_now')

    if buy_now_item:
        try:

            variant = Product_varients.objects.select_related('product').get(id=buy_now_item['variant_id'])
            product = variant.product
        except Product_varients.DoesNotExist:
            return render(request, "errors/product_unavailable.html", status=404)
        
        quantity = buy_now_item['quantity']

        #recomputing price  using offers (don't trust session completely)
        pricing = apply_offer_to_variant(variant)
        price = Decimal(str(pricing['final_price']))
        original_price = Decimal(str(pricing['original_price']))
        discount_per_item = Decimal(str(pricing['discount_amount']))

        if not product.is_listed or not variant.is_listed:
            return render(request, "errors/product_unavailable.html", status=404)

        if variant.stock < quantity:
            messages.error(request, "Not enough stock available.")
            return redirect('checkout')

        subtotal = price * quantity
        discount_amount = discount_per_item * quantity

        coupon_discount = Decimal('0.00')
        if 'coupon_discount' in request.session:
            coupon_discount  = Decimal(request.session['coupon_discount'])


        shipping_charge = Decimal('0.00') if subtotal >= 2000 else Decimal('50.00')
        total_amount = subtotal - coupon_discount + shipping_charge

        selected_address_id= request.session.get('selected_address_id')
        if not selected_address_id:
            messages.error(request, "Please select a delivery address.")
            return redirect('checkout')
        
        shipping_address = get_object_or_404(Address, id=selected_address_id, user=request.user)

        mrp_total = original_price * quantity

        order = Order.objects.create(
            user=request.user,
            shipping_address=shipping_address,
            full_name=shipping_address.full_name,
            mobile=shipping_address.mobile,
            street_address=shipping_address.street_address,
            city=shipping_address.city,
            state=shipping_address.state,
            postal_code=shipping_address.postal_code,
            subtotal=subtotal,
            discount_amount=discount_amount,  #offer discount
            coupon_discount=coupon_discount, #coupon discount
            shipping_charge=shipping_charge,
            total_amount=total_amount,
            payment_method='cod',
            payment_status='pending',
            status='pending',
            order_notes=request.POST.get('order_note', ''),
        )
        order.estimated_delivery = date.today() + timedelta(days=7)
        order.save()

        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.product_name,
            variant=variant,
            variant_colour=variant.colour,
            price=price,
            original_price=original_price,
            discount_amount=discount_per_item,
            quantity=quantity,
            status='pending',
        )

        #reduce stock
        variant.stock -= quantity
        variant.save()

        OrderStatusHistory.objects.create(
            order=order,
            old_status='',
            new_status='pending',
            changed_by=request.user,
            notes='Order placed via Buy Now' 
        )

        #recorde coupon usage
        if 'applied_coupon_id' in request.session:
            try:
                coupon = Coupon.objects.get(id=request.session['applied_coupon_id'])
                discount = Decimal(request.session['coupon_discount'])
                cart_total_before = Decimal(request.session['cart_total_before_coupon'])

                record_coupon_usage(
                    coupon=coupon,
                    uesr=request.user,
                    order=order,
                    discount_amount=discount,
                    cart_total_before_discount=cart_total_before
                )

                del request.session['applied_coupon_id']
                del request.session['coupon_discount']
                del request.session['cart_total_before_coupon']
            except Exception as e:
                print(f"Coupon recording erro: {e}")


        del request.session['buy_now']
        if 'selected_address_id' in request.session:
            del request.session['selected_address_id']
        
        request.session['last_order_id'] = order.id
        messages.success(request, f"Order {order.order_id} placed successfully.")
        return redirect('order_success')

    
    cart = get_or_create_cart(request.user)

    #Validate cart
    is_valid, errors = validate_cart_for_checkout(cart)
    if not is_valid:
        for error in errors:
            messages.error(request, error)
        return redirect('checkout')
    
    #Get address
    selected_address_id = request.session.get('selected_address_id')
    if not selected_address_id:
        messages.error(request, "Please select a delivery address.")
        return redirect('checkout')
    
    shipping_address = get_object_or_404(Address, id=selected_address_id, user=request.user)

    #Calculate totals using offer per variant
    cart_items = cart.items.select_related('product', 'variant').all()
    subtotal = Decimal('0.00')
    total_discount = Decimal('0.00')

    for item in cart_items:
        if not item.product.is_listed or not item.variant.is_listed:
            return render(request, "errors/product_unavailable.html",status=404)
        
        if item.variant.stock <= 0 or item.variant.stock < item.quantity:
            messages.error(request, f"Not enough stock for {item.product.product_name}.")
            return redirect('checkout')

    line_data =[]
    for item in cart_items:
        pricing = apply_offer_to_variant(item.variant)
        final_price = Decimal(str(pricing['final_price']))
        original_price = Decimal(str(pricing['original_price']))
        item_discount = Decimal(str(pricing['discount_amount'])) #per single item

        line_total = final_price * item.quantity
        subtotal += line_total
        total_discount += (item_discount * item.quantity)

        line_data.append({
            'item': item,
            'final_price': final_price,
            'original_price': original_price,
            'item_discount': item_discount,
        })
    
    coupon_discount = Decimal('0.00')
    if 'coupon_discount' in request.session:
        coupon_discount = Decimal(request.session['coupon_discount'])
    
    shipping_charge = Decimal('0.00') if subtotal >= 1000 else Decimal('50.00')
    total_amount = subtotal - coupon_discount + shipping_charge


    mrp_total = Decimal('0.00')

    for item in cart_items:
        pricing = apply_offer_to_variant(item.variant)
        original_price = Decimal(str(pricing['original_price']))
        mrp_total += original_price * item.quantity



    #Create order
    order = Order.objects.create(
        user=request.user,
        shipping_address=shipping_address,
        full_name=shipping_address.full_name,
        mobile=shipping_address.mobile,
        street_address=shipping_address.street_address,
        city=shipping_address.city,
        state=shipping_address.state,
        postal_code=shipping_address.postal_code,
        subtotal=subtotal,
        discount_amount=total_discount,   #offer discount
        coupon_discount=coupon_discount,
        shipping_charge=shipping_charge,
        total_amount=total_amount,
        payment_method='cod',
        payment_status='pending',
        status='pending',
        order_notes=request.POST.get('order_note', ''),
    )
    order.estimated_delivery = date.today() + timedelta(days=7)
    order.save()

    #Create order items
    for d in line_data:
        cart_item = d['item']
        OrderItem.objects.create(
            order=order,
            product=cart_item.product,
            variant=cart_item.variant,
            product_name=cart_item.product.product_name,
            variant_colour=cart_item.variant.colour,
            price=d['final_price'],
            original_price=d['original_price'],
            discount_amount=d['item_discount'],
            quantity=cart_item.quantity,
            status='pending',
        )

        # Reduce stock
        cart_item.variant.stock -= cart_item.quantity
        cart_item.variant.save()

    # Create status history
    OrderStatusHistory.objects.create(
        order=order,
        old_status='',
        new_status='pending',
        changed_by=request.user,
        notes='Order placed successfully.',
    )
    
    if 'applied_coupon_id' in request.session:
        try:
            coupon = Coupon.objects.get(id=request.session['applied_coupon_id'])
            discount = Decimal(request.session['coupon_discount'])
            cart_total_before = Decimal(request.session['cart_total_before_coupon'])

            record_coupon_usage(
                coupon=coupon,
                user=request.user,
                order=order,
                discount_amount=discount,
                cart_total_before_discount=cart_total_before
            )

            del request.session['applied_coupon_id']
            del request.session['coupon_discount']
            del request.session['cart_total_before_coupon']
        except Exception as e:
            print(f"Coupon recording error: {e}")


    # Clear cart
    cart.items.all().delete()
    cart.total = Decimal('0.00')
    cart.save()


    # Clear session
    if 'selected_address_id' in request.session:
        del request.session['selected_address_id']

    # Store order ID for success page
    request.session['last_order_id'] = order.id

    messages.success(request, f"Order {order.order_id} placed successfully.")
    return redirect('order_success')


@login_required(login_url='login')
def order_success(request):
    """Order success page"""
    order_id = request.session.get('last_order_id')

    if not order_id:
        messages.error(request, "No recent order found.")
        return redirect('home')
    
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Clear session
    if 'last_order_id' in request.session:
        del request.session['last_order_id']

    context = {'order': order}
    return render(request, 'orders/order_success.html', context)



@login_required(login_url='login')
def payment_failed(request):
    return render(request, 'orders/payment_failed.html')



@csrf_exempt
@login_required
def toggle_wallet_usage(request):
    if request.method == "POST":
        data = json.loads(request.body)
        request.session["use_wallet"] = data.get("use_wallet", False)
        request.session.modified = True
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "invalid"}, status=400)

