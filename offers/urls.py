from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.offer_dashboard, name="offer_dashboard"),
    path("category/", views.category_offer_list, name="category_offer_list"),
    path("category/add/", views.add_category_offer, name="add_category_offer"),
    path(
        "category/edit/<int:offer_id>/",
        views.edit_category_offer,
        name="edit_category_offer",
    ),
    path(
        "category/delete/<int:offer_id>/",
        views.delete_category_offer,
        name="delete_category_offer",
    ),
    path("product/", views.product_offer_list, name="product_offer_list"),
    path("product/add/", views.add_product_offer, name="add_product_offer"),
    path(
        "product/edit/<int:offer_id>/",
        views.edit_product_offer,
        name="edit_product_offer",
    ),
    path(
        "product/delete/<int:offer_id>/",
        views.delete_product_offer,
        name="delete_product_offer",
    ),
]
