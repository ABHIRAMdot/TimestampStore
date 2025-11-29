from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse
from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP

from .models import Order, OrderItem, OrderStatusHistory
from .forms import CancelOrderForm, CancelOrderItemForm, ReturnOrderItemForm
from .utils import cancel_order, search_orders
from .invoice import generate_invoice_pdf
from accounts.models import Address
from products.models import Product, Product_varients
from cart.models import Cart
from cart.utils import get_or_create_cart, validate_cart_for_checkout




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
    
    paginator = Paginator(orders, 5)
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
    
    if order.status in ['pending', 'cancelled']:
        messages.error(request, "Invoice not available for this order.")
        return redirect('user_order_detail', order_id=order.order_id)
    
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
    
    #save butnow items into session
    request.session['buy_now'] = {
        "product_id":int(product_id),
        "variant_id": int(variant_id),
        'slug': slug,
        "quantity": quantity,
    }

    return redirect('checkout')


# CHECKOUT VIEWS
@login_required(login_url='login')
def checkout_view(request):
    """Display checkout page with addresses and order summery"""

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

        # store buynow items in session
        request.session['buy_now'] = {
            'product_id': product_id,
            'variant_id': variant_id,
            'quantity': quantity,
            'price': float(variant.price)
        }
        
        return redirect('checkout')
    if request.method != 'POST' or not request.POST.get('buy_now_product_id'):
        if 'buy_now' in request.session:
            del request.session['buy_now']
    
    buy_now_item = request.session.get('buy_now')
    if buy_now_item:
        variant = Product_varients.objects.select_related('product').get(id=buy_now_item['variant_id']) 
        product = variant.product
        quantity = buy_now_item['quantity']
        price = Decimal(str(buy_now_item['price'])) 

        #temp cart_items to list in the template loop
        cart_items = [{
            'product': product,
            'variant': variant,
            'product_name': product.product_name,
            'variant_colour': variant.colour,
            'quantity': quantity,
            'price': price,
            'total': price * quantity,
        }]

        subtotal = price * quantity

    else:

        cart = get_or_create_cart(request.user)

        #validate cart
        is_valid, errors = validate_cart_for_checkout(cart)
        if not is_valid:
            for error in errors:
                messages.error(request, error)
            return redirect('cart_view')

        #Calculate total summary
        cart_items = cart.items.select_related('product', 'variant').all()
        subtotal = cart.total
    
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

    #Calculate total discount
    discount_amount = Decimal('0.00')
    for item in cart_items:
        #buy now  item = dict
        if isinstance(item, dict):
            product = item["product"]
            variant = item["variant"]
            price = item["price"]
            quantity =item["quantity"]
        # normal cart item
        else:
            product = item.product
            variant = item.variant
            price = item.price
            quantity = item.quantity

        if product.offer and item.product.offer.is_active:
            original_price = item.variant.price
            discount_per_item = (original_price - price) * item.quantity
            discount_amount += discount_per_item

    # Tax calculation (18% GST example)
    tax_rate = Decimal('0.18')
    # tax_amount = (subtotal - discount_amount) * tax_rate

    #Shipping free above 1000
    shipping_charge = Decimal('0.00') if subtotal >= 1000 else Decimal('50.00')

    # Total amount
    total_amount = subtotal - discount_amount  + shipping_charge  # + tax_amount
    total_amount = total_amount.quantize(Decimal('0'), rounding=ROUND_HALF_UP)
    
    breadcrumbs = [
        {"label": "Home", "url": reverse("home")},
        {"label": "Cart", "url": reverse("cart_view")},
        {"label": "Checkout", "url": None},
    ]
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
        
        'breadcrumbs': breadcrumbs,
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
        price = Decimal(str(buy_now_item['price'])) #float to decimal

        if not product.is_listed or not variant.is_listed:
            return render(request, "errors/product_unavailable.html", status=404)

        if variant.stock < quantity:
            messages.error(request, "Not enough stock available.")
            return redirect('checkout')

        subtotal = price * quantity
        discount_amount = Decimal('0.00')
        shipping_charge = Decimal('0.00') if subtotal >= 2000 else Decimal('50.00')
        total_amount = subtotal + shipping_charge

        selected_address_id= request.session.get('selected_address_id')
        if not selected_address_id:
            messages.error(request, "Please select a delivery address.")
            return redirect('checkout')
        
        shipping_address = get_object_or_404(Address, id=selected_address_id, user=request.user)

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
            discount_amount=discount_amount,
            shipping_charge=shipping_charge,
            total_amount=total_amount,
            payment_method='cod',
            payment_status='pending',
            status='pending',
            order_notes=request.POST.get('order_note', ''),
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

        OrderStatusHistory.objects.create(
            order=order,
            old_status='',
            new_status='pending',
            changed_by=request.user,
            notes='Order placed via Buy Now' 
        )

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

    #Calculate totals
    cart_items = cart.items.select_related('product', 'variant').all()
    subtotal = cart.total

    for item in cart_items:
        if not item.product.is_listed or not item.variant.is_listed:
            return render(request, "errors/product_unavailable.html",status=404)
        
        if item.variant.stock <= 0 or item.variant.stock < item.quantity:
            messages.error(request, f"Not enough stock for {item.product.product_name}.")
            return redirect('checkout')

    discount_amount =Decimal('0.00')
    for item in cart_items:
        if item.product.offer and item.product.offer.is_active:
            original_price = item.variant.price
            discount_per_item = (original_price - item.price) * item.quantity
            discount_amount += discount_per_item
    
    shipping_charge = Decimal('0.00') if subtotal >= 1000 else Decimal('50.00')
    total_amount = subtotal + shipping_charge

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
        discount_amount=discount_amount,
        shipping_charge=shipping_charge,
        total_amount=total_amount,
        payment_method='cod',
        payment_status='pending',
        status='pending',
        order_notes=request.POST.get('order_note', ''),
    )

    #Create order items
    for cart_item in cart_items:
        original_price = cart_item.variant.price
        item_discount = Decimal('0.00')

        if cart_item.product.offer and cart_item.product.offer.is_active:
            item_discount = original_price - cart_item.price

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

        # Reduce stock
        cart_item.variant.stock -=cart_item.quantity
        cart_item.variant.save()

    # Create status history
    OrderStatusHistory.objects.create(
        order=order,
        old_status='',
        new_status='pending',
        changed_by=request.user,
        notes='Order placed successfully.',
    )

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
