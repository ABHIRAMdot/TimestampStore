from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.urls import reverse


from .models import Wishlist, WishlistItem
from products.models import Product, Product_varients
from .utils import (
    get_or_create_wishlist,
    is_product_addable_to_wishlist,
    clean_wishlist_invalid_items,
    is_in_wishlist
)


@login_required(login_url='login')
def wishlist_view(request):
    """Display wishlist items"""
    wishlist = get_or_create_wishlist(request.user)
    
    # Clean invalid items (unlisted products, etc.)
    removed_items = clean_wishlist_invalid_items(wishlist)
    
    if removed_items:
        messages.warning(
            request, 
            f"Some items were removed from your wishlist: {', '.join(removed_items)}"
        )
    
    wishlist_items = wishlist.items.select_related(
        'product', 
        'variant', 
        'product__category',
        'product__offer'
    ).prefetch_related(
        'variant__images'
    ).all()

    breadcrumbs = [
        {"label": "Home", "url": reverse("home")},
        {"label": "All Products", "url": reverse("user_product_list")},
        {"label": "Wishlist", "url": None},
    ]    
    
    context = {
        'wishlist': wishlist,
        'wishlist_items': wishlist_items,
        'wishlist_count': wishlist.get_item_count(),
        'breadcrumbs': breadcrumbs,
    }
    
    return render(request, 'wishlist/wishlist.html', context)


@login_required(login_url='login')
@require_POST
def add_to_wishlist(request):
    """Add product to wishlist"""
    product_id = request.POST.get('product_id')
    variant_id = request.POST.get('variant_id')
    
    # Get product and variant
    product = get_object_or_404(Product, id=product_id)
    variant = None
    
    if variant_id:
        variant = get_object_or_404(Product_varients, id=variant_id, product=product)
    else:
        # If no variant specified, get the first available variant
        variant = product.varients.filter(is_listed=True).first()
        if not variant:
            messages.error(request, "No available variants for this product.")
            return redirect('product_detail', product_id=product_id)
    
    # Check if product can be added to wishlist
    can_add, error_message = is_product_addable_to_wishlist(product, variant)
    if not can_add:
        messages.error(request, error_message)
        return redirect(request.META.get('HTTP_REFERER', 'shop'))
    
    # Use transaction to ensure data consistency
    with transaction.atomic():
        wishlist = get_or_create_wishlist(request.user)
        
        # Check if item already exists in wishlist
        wishlist_item, created = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            product=product,
            variant=variant
        )
        
        if created:
            messages.success(
                request,
                f"{product.product_name} added to your wishlist."
            )
        else:
            messages.info(
                request,
                f"{product.product_name} is already in your wishlist."
            )
    
    # Return to previous page or product detail
    return redirect(request.META.get('HTTP_REFERER', 'wishlist_view'))


@login_required(login_url='login')
@require_POST
def remove_from_wishlist(request):
    """Remove item from wishlist"""
    wishlist_item_id = request.POST.get('wishlist_item_id')
    
    wishlist_item = get_object_or_404(
        WishlistItem,
        id=wishlist_item_id,
        wishlist__user=request.user
    )
    
    product_name = wishlist_item.product.product_name
    wishlist_item.delete()
    
    messages.success(request, f"{product_name} removed from your wishlist.")
    return redirect('wishlist_view')


@login_required(login_url='login')
@require_POST
def toggle_wishlist(request):
    """Toggle product in wishlist (add if not exists, remove if exists) - AJAX"""
    product_id = request.POST.get('product_id')
    variant_id = request.POST.get('variant_id')
    
    try:
        product = get_object_or_404(Product, id=product_id)
        variant = None
        
        if variant_id:
            variant = get_object_or_404(Product_varients, id=variant_id, product=product)
        else:
            variant = product.varients.filter(is_listed=True).first()
        
        if not variant:
            return JsonResponse({
                'success': False,
                'message': 'No available variants for this product.'
            })
        
        wishlist = get_or_create_wishlist(request.user)
        
        # Check if item exists
        existing_item = WishlistItem.objects.filter(
            wishlist=wishlist,
            product=product,
            variant=variant
        ).first()
        
        if existing_item:
            # Remove from wishlist
            existing_item.delete()
            return JsonResponse({
                'success': True,
                'action': 'removed',
                'message': f'{product.product_name} removed from wishlist.',
                'in_wishlist': False
            })
        else:
            # Check if can add
            can_add, error_message = is_product_addable_to_wishlist(product, variant)
            if not can_add:
                return JsonResponse({
                    'success': False,
                    'message': error_message
                })
            
            # Add to wishlist
            WishlistItem.objects.create(
                wishlist=wishlist,
                product=product,
                variant=variant
            )
            return JsonResponse({
                'success': True,
                'action': 'added',
                'message': f'{product.product_name} added to wishlist.',
                'in_wishlist': True
            })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred. Please try again.'
        })


@login_required(login_url='login')
@require_POST
def move_to_cart(request):
    """Move item from wishlist to cart"""
    wishlist_item_id = request.POST.get('wishlist_item_id')
    
    wishlist_item = get_object_or_404(
        WishlistItem,
        id=wishlist_item_id,
        wishlist__user=request.user
    )
    
    # Check if product is available
    if not wishlist_item.is_product_available():
        messages.error(request, "This product is no longer available.")
        wishlist_item.delete()
        return redirect('wishlist_view')
    
    # Check if in stock
    if not wishlist_item.is_in_stock():
        messages.error(request, "This product is out of stock.")
        return redirect('wishlist_view')
    
    # Import here to avoid circular import
    from cart.models import Cart, CartItem
    from cart.utils import get_or_create_cart, get_discounted_price
    
    with transaction.atomic():
        cart = get_or_create_cart(request.user)
        
        # Get current price
        current_price = get_discounted_price(wishlist_item.product, wishlist_item.variant)
        
        # Check if item already exists in cart
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=wishlist_item.product,
            variant=wishlist_item.variant,
            defaults={
                'quantity': 1,
                'price': current_price
            }
        )
        
        if not created:
            # Item already in cart, just increase quantity if possible
            if cart_item.can_increase_quantity():
                cart_item.quantity += 1
                cart_item.save()
                messages.success(
                    request,
                    f"Increased quantity of {wishlist_item.product.product_name} in cart."
                )
            else:
                messages.info(
                    request,
                    f"{wishlist_item.product.product_name} is already in your cart."
                )
        else:
            messages.success(
                request,
                f"{wishlist_item.product.product_name} moved to cart."
            )
        
        # Remove from wishlist
        wishlist_item.delete()
        
        # Recalculate cart total
        cart.calculate_total()
    
    return redirect('wishlist_view')


@login_required(login_url='login')
def move_all_to_cart(request):
    """Move all available wishlist items to cart"""
    wishlist = get_or_create_wishlist(request.user)
    wishlist_items = wishlist.items.all()
    
    if not wishlist_items.exists():
        messages.info(request, "Your wishlist is empty.")
        return redirect('wishlist_view')
    
    # Import here to avoid circular import
    from cart.models import Cart, CartItem
    from cart.utils import get_or_create_cart, get_discounted_price
    
    moved_count = 0
    skipped_items = []
    
    with transaction.atomic():
        cart = get_or_create_cart(request.user)
        
        for item in wishlist_items:
            # Check if available and in stock
            if not item.is_product_available() or not item.is_in_stock():
                skipped_items.append(item.product.product_name)
                continue
            
            # Get current price
            current_price = get_discounted_price(item.product, item.variant)
            
            # Add to cart or increase quantity
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=item.product,
                variant=item.variant,
                defaults={
                    'quantity': 1,
                    'price': current_price
                }
            )
            
            if not created and cart_item.can_increase_quantity():
                cart_item.quantity += 1
                cart_item.save()
            
            # Remove from wishlist
            item.delete()
            moved_count += 1
        
        # Recalculate cart total
        cart.calculate_total()
    
    if moved_count > 0:
        messages.success(
            request,
            f"{moved_count} item(s) moved to cart."
        )
    
    if skipped_items:
        messages.warning(
            request,
            f"Some items couldn't be moved: {', '.join(skipped_items)}"
        )
    
    return redirect('cart_view')


@login_required(login_url='login')
def clear_wishlist(request):
    """Clear all items from wishlist"""
    wishlist = get_or_create_wishlist(request.user)
    wishlist.items.all().delete()
    
    messages.success(request, "Your wishlist has been cleared.")
    return redirect('wishlist_view')


# AJAX endpoint for wishlist count (for navbar)
@login_required(login_url='login')
def get_wishlist_count(request):
    """Get wishlist item count for AJAX requests"""
    wishlist = get_or_create_wishlist(request.user)
    return JsonResponse({'count': wishlist.get_item_count()})


# Check if product is in wishlist (AJAX)
@login_required(login_url='login')
def check_wishlist_status(request):
    """Check if product/variant is in wishlist"""
    product_id = request.GET.get('product_id')
    variant_id = request.GET.get('variant_id')
    
    if not product_id:
        return JsonResponse({'in_wishlist': False})
    
    try:
        product = Product.objects.get(id=product_id)
        variant = None
        
        if variant_id:
            variant = Product_varients.objects.get(id=variant_id)
        
        in_wishlist = is_in_wishlist(request.user, product, variant)
        
        return JsonResponse({'in_wishlist': in_wishlist})
    except:
        return JsonResponse({'in_wishlist': False})