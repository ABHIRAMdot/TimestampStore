from .models import Cart

def cart_count(request):
    """Add cart count to all templates"""
    cart_item_count = 0
    
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user, status='active')
            cart_item_count = cart.get_item_count()
        except Cart.DoesNotExist:
            cart_item_count = 0
    
    return {
        'cart_item_count': cart_item_count
    }