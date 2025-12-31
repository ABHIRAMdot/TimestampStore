from .models import Wishlist, WishlistItem


def get_or_create_wishlist(user):
    """Get or create wishlist for a user"""
    wishlist, created = Wishlist.objects.get_or_create(user=user)
    return wishlist


def is_product_addable_to_wishlist(product, variant=None):
    """
    Check if product can be added to wishlist
    Returns: (bool, str) - (can_add, error_message)
    """
    # Check if product is listed
    if not product.is_listed:
        return False, "This product is currently unavailable."

    # Check if category is listed
    if product.category and not product.category.is_listed:
        return False, "This product category is currently unavailable."

    # Check variant if provided
    if variant:
        # Check if variant is listed
        if not variant.is_listed:
            return False, "This product variant is currently unavailable."

    return True, ""


def clean_wishlist_invalid_items(wishlist):
    """
    Remove items from wishlist that are no longer available
    Returns: list of removed item names
    """
    removed_items = []

    for item in wishlist.items.all():
        if not item.is_product_available():
            removed_items.append(str(item))
            item.delete()

    return removed_items


def is_in_wishlist(user, product, variant=None):
    """Check if a product/variant is in user's wishlist"""
    try:
        wishlist = Wishlist.objects.get(user=user)
        if variant:
            return wishlist.items.filter(product=product, variant=variant).exists()
        return wishlist.items.filter(product=product).exists()
    except Wishlist.DoesNotExist:
        return False
