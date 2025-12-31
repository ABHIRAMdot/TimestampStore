from django.urls import path
from . import views

urlpatterns = [
    path("", views.home_page, name="home"),
    path("shop/", views.user_product_list, name="user_product_list"),
    path("product/<slug:slug>/", views.user_product_detail, name="product_detail"),
    path("product-unavailable/", views.product_unavailable, name="product_unavailable"),
]
