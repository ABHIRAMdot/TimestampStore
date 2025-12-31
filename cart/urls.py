from django.urls import path
from . import views

urlpatterns = [
    path("", views.cart_view, name="cart_view"),
    path("add/", views.add_to_cart, name="add_to_cart"),
    # path('update/', views.update_cart_quantity, name='update_cart_quantity'),
    # path('remove/', views.remove_from_cart, name='remove_from_cart'),
    # path('clear/', views.clear_cart, name='clear_cart'),
    path("checkout/", views.proceed_to_checkout, name="proceed_to_checkout"),
    path("count/", views.get_cart_count, name="get_cart_count"),
    # ajax urls
    path(
        "ajax/update/",
        views.update_cart_quantity_ajax,
        name="update_cart_quantity_ajax",
    ),
    path("ajax/remove/", views.remove_from_cart_ajax, name="remove_from_cart_ajax"),
    path("ajax/clear/", views.clear_cart_ajax, name="clear_cart_ajax"),
    # path('add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    # path('remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
]
