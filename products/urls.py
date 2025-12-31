from django.urls import path
from . import views


urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("add/", views.add_product, name="add_product"),
    path("edit/<int:product_id>/", views.edit_product, name="edit_product"),
    # path('toggle-product-status/<int:product_id>/', views.toggle_product_status, name='toggle_product_status'),
    path("view/<int:product_id>/", views.view_product, name="view_product"),
    # Variant URLs
    # path('variants/', views.variants_dashboard, name='variants_dashboard'),
    path(
        "products/<int:product_id>/variants/",
        views.manage_variants,
        name="manage_variants",
    ),
    path(
        "variants/toggle/<int:variant_id>/",
        views.toggle_variant_status,
        name="toggle_variant_status",
    ),
]
