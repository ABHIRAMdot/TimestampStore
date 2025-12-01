from decimal import Decimal
from django.db.models import Q
from .models import Cart, CartItem


def get_or_create_cart(user):
    """Get or create cart for a user"""
    cart, created = Cart.objects.get_or_create(

        user=user,
        status='active',
        defaults={'total': Decimal('0.00')}
    )
    return cart


def is_product_addable_to_cart(product, variant=None):
    """
    Check if product can be added to cart
    Return: (bool, str) - (can_add, error_message)
    """
    if not product.is_listed:
        return False, "This product is currently unavailable."
    
    if product.category and not product.category.is_listed:
        return False, "This product category is currently unavialable."
    
    #check variant if provided
    if variant:
        if not variant.is_listed:
            return False, "This product variant is currently unavailable."
        
        #check if variant has stock
        if variant.stock <= 0:
            return False, "This product is out of stock"
    
    return True, ""


def get_discounted_price(product, variant):
    """
    Calculate the discounted price if offer exists
    Return: Decimal price
    """
    base_price = variant.price if variant else product.base_price

    #check if product has an active offer
    if product.offer and product.offer.is_active:
        discount_percentage = product.offer.discount
        discount_amount = (base_price * discount_percentage) / 100
        return base_price - discount_amount
    
    return base_price


def remove_from_wishlist_if_exists(user, product, variant=None):
    """Remove product from wishlist if it exists"""
    try:
        from wishlist.models import WishlistItem, Wishlist

        #check if wishlist exists
        wishlist = Wishlist.objects.filter(user=user).first()
        if not wishlist:
            return False

        filters = {'wishlist':wishlist,'product':product}
        if variant:
            filters['variant'] = variant

        delete_count, _ = WishlistItem.objects.filter(**filters).delete()
        return delete_count > 0
    except Exception as e:
        # Wishlist app might exists or other error
        print(f"Error removing from wishlist: {e}")
        return False
    

def clean_cart_invalid_items(cart):
    """Remove items from cart that are no longer available 
    Returns: List of removed item names
    """

    removed_items = []
    
    for item in cart.items.all():
        if not item.is_product_available() or not item.is_in_stock():
            removed_items.append(str(item))
            # item.delete()

    if removed_items:
        cart.calculate_total()
    
    return removed_items


def validate_cart_for_checkout(cart):
    """
    Validate all cart items before checkout
    Returns: (bool, list) - (is_valid, error_messages)
    """
    errors = []

    if not cart.items.exists():
        errors.append("Your cart is empty.")
        return False, errors
    
    for item in cart.items.all():
        #check if product/ variant is available
        if not item.is_product_available():
            errors.append(f"{item.product.product_name} is no longer available.")

        #check stock
        elif not item.is_in_stock():
            errors.append(f"{item.product.product_name} is out of stock.")

        #Check if quantity exceeds stock
        elif item.quantity > item.get_available_stock():
            errors.append(
                f"{item.product.product_name} – Only {item.get_available_stock()} items available, but you have {item.quantity} in cart.")
    return len(errors) == 0, errors
