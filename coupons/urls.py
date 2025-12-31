from django.urls import path
from . import views

urlpatterns = [
    # Coupon List & Management
    path("admin/coupons/", views.coupon_list, name="coupon_list"),
    path("admin/coupons/add/", views.add_coupon, name="add_coupon"),
    path("admin/coupons/edit/<int:coupon_id>/", views.edit_coupon, name="edit_coupon"),
    path(
        "admin/coupons/delete/<int:coupon_id>/",
        views.delete_coupon,
        name="delete_coupon",
    ),
    # Coupon Actions
    path(
        "admin/coupons/toggle/<int:coupon_id>/",
        views.toggle_coupon_status,
        name="toggle_coupon_status",
    ),
    path(
        "admin/coupons/usage/<int:coupon_id>/",
        views.coupon_usage_history,
        name="coupon_usage_history",
    ),
    # User coupon views
    path("available/", views.user_available_coupons, name="user_available_coupons"),
    path(
        "my-usage/", views.user_coupon_usage_history, name="user_coupon_usage_history"
    ),
]
