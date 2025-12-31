from django.urls import path
from . import views

urlpatterns = [
    path("", views.wallet_dashboard, name="wallet_dashboard"),
    path(
        "add-money/create-order/",
        views.add_money_create_order,
        name="add_money_create_order",
    ),
    path(
        "add-money/verify-payment/",
        views.add_money_verify_payment,
        name="add_money_verify_payment",
    ),
    path("admin/wallet-view/", views.admin_wallet_view, name="admin_wallet_view"),
    path(
        "admin/wallet/<int:wallet_id>/",
        views.admin_wallet_history,
        name="admin_wallet_history",
    ),
]
