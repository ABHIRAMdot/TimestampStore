from django.urls import path, include
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('resend-reset-otp/', views.resend_reset_otp, name='resend_reset_otp'),


    #  Consistent Password Reset URLs
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/', views.reset_password, name='reset_password'),

    # Resend OTP (for registration)
    path('resend-otp/', views.resend_otp, name='resend_otp'),
]
