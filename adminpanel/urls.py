from django.urls import path
from . import views
from products.views import toggle_product_status

# from orders.admin_views import admin_orders_list, admin_order_detail, admin_approve_return, admin_inventory_management, admin_update_stock
from orders import admin_views

urlpatterns = [
    path("", views.admin_login, name="admin_login"),
    path("admin-dashboard", views.admin_dashboard, name="admin_dashboard"),
    path("users-list", views.user_list, name="user_list"),
    path(
        "users-list/toggle-user-status/<int:user_id>/",
        views.toggle_user_status,
        name="toggle_user_status",
    ),
    path(
        "admin-logout",
        views.admin_logout,
        name="admin_logout",
    ),
    path("sales_report/", views.admin_sales_report, name="admin_sales_report"),
    path(
        "products/toggle-product-status/<int:product_id>/",
        toggle_product_status,
        name="toggle_product_status",
    ),
    # Order Management
    path("orders/", admin_views.admin_orders_list, name="admin_orders_list"),
    path(
        "orders/<str:order_id>/",
        admin_views.admin_order_detail,
        name="admin_order_detail",
    ),
    path(
        "orders/item/<int:item_id>/approve-return/",
        admin_views.admin_approve_return,
        name="admin_approve_return",
    ),
    path(
        "orders/<str:order_id>/invoice/",
        admin_views.admin_download_invoice,
        name="admin_download_invoice",
    ),
    # Inventory Management
    path("inventory/", admin_views.admin_inventory_management, name="admin_inventory"),
    path(
        "inventory/update/<int:variant_id>/",
        admin_views.admin_update_stock,
        name="admin_update_stock",
    ),
    path(
        "admin/returns/",
        admin_views.admin_return_requests_list,
        name="admin_return_requests_list",
    ),
    path(
        "admin/return/<int:item_id>/approve/",
        admin_views.admin_approve_return,
        name="admin_approve_return",
    ),
    path(
        "admin/return/<int:item_id>/reject/",
        admin_views.admin_reject_return,
        name="admin_reject_return",
    ),
]
