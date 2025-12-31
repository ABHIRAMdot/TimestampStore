from django.urls import path
from . import views

# All order-related URLs
urlpatterns = [
    # ========== USER SIDE URLs ==========
    path("my-orders/", views.user_orders_list, name="user_orders_list"),
    path(
        "my-orders/<str:order_id>/", views.user_order_detail, name="user_order_detail"
    ),
    path(
        "my-orders/<str:order_id>/cancel/", views.cancel_order_view, name="cancel_order"
    ),
    path(
        "my-orders/item/<int:item_id>/cancel/",
        views.cancel_order_item_view,
        name="cancel_order_item",
    ),
    path(
        "my-orders/item/<int:item_id>/return/",
        views.return_order_item_view,
        name="return_order_item",
    ),
    path(
        "my-orders/<str:order_id>/invoice/",
        views.download_invoice,
        name="download_invoice",
    ),
    # CHECKOUT URLs
    path("checkout/", views.checkout_view, name="checkout"),
    path("buy-now/", views.buy_now, name="buy_now"),
    path(
        "select-address/<int:address_id>/", views.select_address, name="select_address"
    ),
    path("place-order/", views.place_order, name="place_order"),
    path("order-success/", views.order_success, name="order_success"),
    path("payment-failed/", views.payment_failed, name="payment_failed"),
    path("toggle-wallet/", views.toggle_wallet_usage, name="toggle_wallet_usage"),
]
