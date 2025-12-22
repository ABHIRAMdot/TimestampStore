from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from decimal import Decimal
from django.urls import reverse, NoReverseMatch
from datetime import date, timedelta

import logging
from .models import Cart, CartItem
from products.models import Product, Product_varients
from .utils import(
    get_or_create_cart,
    is_product_addable_to_cart,
    get_discounted_price,
    remove_from_wishlist_if_exists,
    clean_cart_invalid_items,
    validate_cart_for_checkout
)

from offers.utils import apply_offer_to_variant


logger = logging.getLogger('project_logger')

# AJAX: update quantity
@login_required(login_url='login')
@require_POST
def update_cart_quantity_ajax(request):
    """AJAX increase/decrease quantity of a cart item, return jason"""
    cart_item_id = request.POST.get('cart_item_id')
    action = request.POST.get('action')  # 'increase' or 'decrease'
    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)

    # Re-check availability
    if not cart_item.is_product_available():
        # remove item server-side if not available
        product_name = cart_item.product.product_name
        cart_item.delete()
        cart = get_or_create_cart(request.user)
        cart.calculate_total()
        return JsonResponse({
            'success': False,
            'message': f"{product_name} is no longer available and was removed from your cart.",
            'cart_total': str(cart.total),
            'cart_count': cart.get_item_count(),
            'removed': True,
            'cart_item_id': cart_item_id
        })

    with transaction.atomic():
        if action == 'increase':
            # check stock
            if cart_item.quantity >= cart_item.get_available_stock():
                return JsonResponse({
                    'success': False,
                    'message': f"Cannot add more. Only {cart_item.get_available_stock()} items available.",
                    'cart_total': str(cart_item.cart.total),
                    'cart_count': cart_item.cart.get_item_count(),
                })
            if cart_item.quantity >= CartItem.MAX_QUANTITY_PER_PRODUCT:
                return JsonResponse({
                    'success': False,
                    'message': f"Maximum {CartItem.MAX_QUANTITY_PER_PRODUCT} items allowed per product.",
                    'cart_total': str(cart_item.cart.total),
                    'cart_count': cart_item.cart.get_item_count(),
                })

            cart_item.quantity += 1
            cart_item.save()
            cart_item.cart.calculate_total()

            offer_data = apply_offer_to_variant(cart_item.variant)

            total_savings = Decimal('0')
            subtotal_before_discount = Decimal('0')
            for it in cart_item.cart.items.all():
                offer = apply_offer_to_variant(it.variant)
                total_savings += (offer['original_price'] - offer['final_price']) * it.quantity
                subtotal_before_discount += offer['original_price'] * it.quantity


            # subtotal_before_discount = sum(
            #     item.original_price * item.quantity
            #     for item in cart_item.cart.items.all()
            # )

            return JsonResponse({
                'success': True,
                'message': f"Quantity updated to {cart_item.quantity}.",
                'cart_item_id': cart_item_id,
                'new_quantity': cart_item.quantity,
                
                'original_price': str(offer_data['original_price']),
                'discount_amount': str(offer_data['discount_amount']),
                'final_price': str(offer_data['final_price']),
                'discount_percentage': str(offer_data['discount_percentage']),

                'item_subtotal': str(cart_item.get_subtotal()),
                'cart_total': str(cart_item.cart.total),
                'cart_count': cart_item.cart.get_item_count(),

                'line_discount': str(offer_data['original_price'] - offer_data['final_price']),
                'item_savings': str(
                    (offer_data['original_price'] - offer_data['final_price']) * cart_item.quantity
                ),

                'cart_savings': str(total_savings),

                'subtotal_before_discount': str(subtotal_before_discount),

            })

        elif action == 'decrease':
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()
                cart_item.cart.calculate_total()


                offer_data = apply_offer_to_variant(cart_item.variant)

                total_savings = Decimal('0')
                subtotal_before_discount = Decimal('0')
                for it in cart_item.cart.items.all():
                    offer = apply_offer_to_variant(it.variant)
                    total_savings += (offer['original_price'] - offer['final_price']) * it.quantity
                    subtotal_before_discount += offer['original_price'] * it.quantity


                # subtotal_before_discount = sum(
                #     item.original_price * item.quantity
                #     for item in cart_item.cart.items.all()
                # )                

                return JsonResponse({
                    'success': True,
                    'message': f"Quantity updated to {cart_item.quantity}.",
                    'cart_item_id': cart_item_id,
                    'new_quantity': cart_item.quantity,

                    'original_price': str(offer_data['original_price']),
                    'discount_amount': str(offer_data['discount_amount']),
                    'final_price': str(offer_data['final_price']),
                    'discount_percentage': str(offer_data['discount_percentage']),  

                    'item_subtotal': str(cart_item.get_subtotal()),
                    'cart_total': str(cart_item.cart.total),
                    'cart_count': cart_item.cart.get_item_count(),

                    'line_discount': str(offer_data['original_price'] - offer_data['final_price']),
                    'item_savings': str(
                        (offer_data['original_price'] - offer_data['final_price']) * cart_item.quantity
                    ),

                    'cart_savings': str(total_savings),

                    'subtotal_before_discount': str(subtotal_before_discount),
                })
            else:
                # If qty==1 and user requested decrease -> remove item
                product_name = cart_item.product.product_name
                cart = cart_item.cart
                cart_item.delete()
                cart.calculate_total()

                total_savings = Decimal('0')
                subtotal_before_discount = Decimal('0')
                for it in cart.items.all():
                    offer = apply_offer_to_variant(it.variant)
                    total_savings += (offer['original_price'] - offer['final_price']) * it.quantity
                    subtotal_before_discount += offer['original_price'] * it.quantity

                return JsonResponse({
                    'success': True,
                    'message': f"{product_name} removed from cart.",
                    'removed': True,
                    'cart_total': str(cart.total),
                    'cart_count': cart.get_item_count(),
                    'cart_item_id': cart_item_id,

                    'cart_savings': str(total_savings),
                    'subtotal_before_discount': str(subtotal_before_discount),
                })

    return JsonResponse({'success': False, 'message': 'Invalid action.'})


#  AJAX: remove item
@login_required(login_url='login')
@require_POST
def remove_from_cart_ajax(request):
    cart_item_id = request.POST.get('cart_item_id')
    cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)
    product_name = cart_item.product.product_name
    cart = cart_item.cart
    cart_item.delete()
    cart.calculate_total()

    total_savings = Decimal('0')
    subtotal_before_discount = Decimal('0')
    for it in cart.items.all():
        offer = apply_offer_to_variant(it.variant)
        total_savings += (offer['original_price'] - offer['final_price']) * it.quantity
        subtotal_before_discount += offer['original_price'] * it.quantity

    return JsonResponse({
        'success': True,
        'message': f"{product_name} removed from your cart.",
        'cart_total': str(cart.total),
        'cart_count': cart.get_item_count(),
        'cart_item_id': cart_item_id,

        'cart_savings': str(total_savings),
        'subtotal_before_discount': str(subtotal_before_discount),
    })


#  AJAX: clear cart
@login_required(login_url='login')
@require_POST
def clear_cart_ajax(request):
    cart = get_or_create_cart(request.user)
    cart.items.all().delete()
    cart.total = Decimal('0.00')
    cart.save()
    return JsonResponse({
        'success': True,
        'message': 'Your cart has been cleared.',
        'cart_total': str(cart.total),
        'cart_count': cart.get_item_count(),
        'cart_savings': "0",
        'subtotal_before_discount': "0",
    })



@login_required
def cart_view(request):
    """Display cart items"""
    cart = get_or_create_cart(request.user)
    cart.calculate_total()
    
    cart_items = cart.items.select_related('product', 'variant', 'product__category').all()
    
    
    for item in cart_items:
        if not item.variant.product.is_listed or not item.variant.is_listed or item.variant.stock <= 0:
            item.unavailable = True
            item.original_price = item.price
            item.discount_amount = Decimal('0.00')
        else:
            item.unavailable = False

            offer_data = apply_offer_to_variant(item.variant)

            item.original_price = offer_data['original_price']
            item.discount_amount = offer_data['discount_amount']
            item.final_price = offer_data['final_price']
            item.discount_percentage = offer_data.get('discount_percentage', 0)

    
    subtotal_before_discount = sum(
            item.original_price * item.quantity
            for item in cart_items
        )


    total_savings = sum(
        (item.original_price - item.final_price) * item.quantity
        for item in cart_items
        )



    breadcrumbs = [
        {"label": "Home", "url": reverse("home")},
        {"label": "All Products", "url": reverse("user_product_list")},
        {"label": "Cart", "url": None},
    ]    

    estimated_delivery = date.today() + timedelta(days=7)

    context = {
        'cart': cart,
        'cart_items': cart_items, 
        'cart_count': cart.get_item_count(),
        'breadcrumbs': breadcrumbs,
        'any_unavailable': any(item.unavailable for item in cart_items),
        'estimated_delivery': estimated_delivery,
        'total_savings': total_savings,     
        'subtotal_before_discount': subtotal_before_discount,

        }
    return render(request, 'cart/cart.html', context)


@login_required(login_url='login')
@require_POST
def add_to_cart(request):
    """Add product to cart"""
    logger.info("Add to cart function called")
    # logger.debug(f"User: {request.user.email}")
    # logger.warning("Test warning message")
    # logger.error("Something went wrong in add_to_cart")

    product_id = request.POST.get('product_id')
    variant_id = request.POST.get('variant_id')
    quantity = int(request.POST.get('quantity', 1))

    #Validate quantity
    if quantity < 1:
        messages.error(request, "Invalid quantity.")
        return redirect('product_detail', slug=product.slug)
    
    #Get product and variant
    product = get_object_or_404(Product, id=product_id)
    variant = None

    if variant_id:
        variant = get_object_or_404(Product_varients, id=variant_id, product=product)
    else:
        messages.error(request, "Please select a color variant.")
        return redirect('product_detail', slug=product.slug)
    
    #Check if product can be added to cart 
    can_add, error_message = is_product_addable_to_cart(product, variant)
    if not can_add:
        messages.error(request, error_message)
        return redirect('product_detail', slug=product.slug)
    
    if quantity > variant.stock:
        messages.error(request, f" Only {variant.stock} items available in stock.")
        return redirect('product_detail', slug=product.slug)

    if quantity > CartItem.MAX_QUANTITY_PER_PRODUCT:
        messages.error(request, f"Maximum {CartItem.MAX_QUANTITY_PER_PRODUCT} items allowed per product.")
        return redirect('product_detail', slug=product.slug)

    # transaction to ensure data consistancy 
    with transaction.atomic():
        cart = get_or_create_cart(request.user)

        #Get current price (with discount if applicable)
        current_price = get_discounted_price(product, variant)

        #Check if item already exists in cart
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={
                'quantity': quantity,
                'price': current_price
            }
        )

        if not created:
            # Item already exists, increase quantity
            new_quantity = cart_item.quantity + quantity

            #Check against stock
            if new_quantity > variant.stock:
                messages.error(request, f"Cannot add more. Only {variant.stock} items available.")
                return redirect('product_detail', slug=product.slug) 
            
            if new_quantity > CartItem.MAX_QUANTITY_PER_PRODUCT:
                messages.error(request,
                    f"Cannot add more. Maximum {CartItem.MAX_QUANTITY_PER_PRODUCT} "
                    f"items allowed per product."
                )
                return redirect('product_detail', slug=product.slug)                

            cart_item.quantity = new_quantity
            cart_item.price = current_price        # Update price in case of offer changes
            cart_item.save()

            messages.success(request, f"Increased quantity of {product.product_name} in your cart.")
        else:
            messages.success(request, f"{product.product_name} added to your cart.")

        #remove from wishlist if exists
        remove_from_wishlist_if_exists(request.user, product, variant)

        # recalculate cart total
        cart.calculate_total()

    try:
        product = Product.objects.filter(id=product.id).first()
        if not product or not product.is_listed or (product.category and not product.category.is_listed):
            # product just became unavailable
            context = {
                'product_name': getattr(product, 'product_name', 'This product'),
                'product': product,
            }
            return render(request, 'errors/product_unavailable.html', context, status=410)

        # OK product is available - redirect to detail using slug (match urlconf)
        return redirect(f"/product/{product.slug}/?variant={variant.id}")

    except NoReverseMatch:
        messages.info(request, "Product added to cart. You can continue shopping.")
        
        return redirect('user_product_list')        



# @login_required(login_url='login')
# @require_POST
# def update_cart_quantity(request):
#     """Update cart item quantity (increment/decrement)"""
#     cart_item_id = request.POST.get('cart_item_id')
#     action = request.POST.get('action')  # increasse or decrease

#     cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)


#     # Check if product is still available
#     if not cart_item.is_product_available():
#         messages.error(request, "This product is no longer available.")
#         cart_item.delete()
#         cart_item.cart.calculate_total()
#         return redirect('cart_view') 
    
#     with transaction.atomic():
#         if action == 'increase':
#             # check if can increase
#             if not cart_item.can_increase_quantity():
#                 if cart_item.quantity >= cart_item.variant.stock:
#                     messages.error(request, f"Cannot add more. Only {cart_item.variant.stock} items available.")
#                 elif cart_item.quantity >= CartItem.MAX_QUANTITY_PER_PRODUCT:
#                     messages.error(request, f"Maximum {CartItem.MAX_QUANTITY_PER_PRODUCT} items allowed.")
#                     return redirect('cart_view')

#             cart_item.quantity +=1
#             cart_item.save()
#             messages.success(request, "Quantity increased.")

#         elif action == 'decrease':
#             if cart_item.quantity > 1:
#                 cart_item.quantity -= 1
#                 cart_item.save()
#                 messages.success(request, f"Quantity decreased.")
#             else:
#                 # if quantity is 1, remove item instead
#                 product_name = cart_item.product.product_name
#                 cart_item.delete()
#                 messages.success(request, f"{product_name} removed from cart")

#         # Recalculate total
#         cart_item.cart.calculate_total()

#     return redirect('cart_view')


# @login_required(login_url='login')
# @require_POST
# def remove_from_cart(request):
#     """Remove item from cart"""
#     cart_item_id = request.POST.get('cart_item_id')

#     cart_item = get_object_or_404(CartItem, id=cart_item_id, cart__user=request.user)

#     product_name = cart_item.product.product_name
#     cart = cart_item.cart

#     cart_item.delete()
#     cart.calculate_total()

#     messages.success(request, f"{product_name} removed from your cart.")
#     return redirect('cart_view')


# @login_required(login_url='login')
# def clear_cart(request):
#     """Clear all items from cart"""
#     cart = get_or_create_cart(request.user)
#     cart.items.all().delete()
#     cart.total = Decimal('0.00')
#     cart.save()

#     messages.success(request, "Your cart has been cleared.")
#     return redirect('car_view')


@login_required(login_url='login')
def proceed_to_checkout(request):
    """Validate cart and proceed to checkout"""
    cart = get_or_create_cart(request.user)

    #Validate cart
    is_valid, errors = validate_cart_for_checkout(cart)

    if not is_valid:
        for error in errors:
            messages.error(request, error)
        return redirect('cart_view')
    
    # If valid, redirect to checkout
    return redirect('checkout')


# AJAX endpoint for cart count (for navbar)
@login_required(login_url='login')
def get_cart_count(request):
    """Get cart item count for AJAX requests"""
    cart = get_or_create_cart(request.user)
    return JsonResponse({'count': cart.get_item_count()})