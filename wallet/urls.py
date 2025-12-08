from django.urls import path
from . import views

urlpatterns = [
    path('',views.wallet_dashboard, name='wallet_dashboard'),

    path('add-money/create-order/', views.add_money_create_order, name='add_money_create_order'),
    path('add-money/verify-payment/', views.add_money_verify_payment, name='add_money_verify_payment'),
]