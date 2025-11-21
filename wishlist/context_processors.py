from .models import Wishlist

def wishlist_count(request):
    """Add wishlist count to all templates"""
    wishlist_item_count = 0
    
    if request.user.is_authenticated:
        try:
            wishlist = Wishlist.objects.get(user=request.user)
            wishlist_item_count = wishlist.get_item_count()
        except Wishlist.DoesNotExist:
            wishlist_item_count = 0
    
    return {
        'wishlist_item_count': wishlist_item_count
    }