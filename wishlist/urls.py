from django.urls import path
from . import views

urlpatterns = [
    path("", views.wishlist_view, name="wishlist_view"),
    path("add/", views.add_to_wishlist, name="add_to_wishlist"),
    path("remove/", views.remove_from_wishlist, name="remove_from_wishlist"),
    path("toggle/", views.toggle_wishlist, name="toggle_wishlist"),
    path("move-to-cart/", views.move_to_cart, name="move_to_cart"),
    path("move-all-to-cart/", views.move_all_to_cart, name="move_all_to_cart"),
    path("clear/", views.clear_wishlist, name="clear_wishlist"),
    path("count/", views.get_wishlist_count, name="get_wishlist_count"),
    path("check-status/", views.check_wishlist_status, name="check_wishlist_status"),
]
