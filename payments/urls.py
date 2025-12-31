from django.urls import path
from . import views

urlpatterns = [
    path("create-order/", views.create_razorpay_order, name="create_razorpay_order"),
    path("verify-payment/", views.verify_payment, name="verify_payment"),
]
