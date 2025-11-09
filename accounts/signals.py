from django.dispatch import receiver
from allauth.socialaccount.signals import pre_social_login
from allauth.account.signals import user_signed_up
from django.contrib import messages
from .models import Account
from django.core.mail import send_mail
from django.conf import settings

@receiver(pre_social_login)
def link_to_local_user(sender, request, sociallogin, **kwargs):
    """
    When user logs in via Google, link to existing Account if email matches
    """
    email = sociallogin.account.extra_data.get('email')
    if email:
        try:
            # Check if user already exists with this email
            existing_user = Account.objects.get(email=email)
            
            # If user exists but hasn't verified OTP yet, don't allow Google login
            if not existing_user.is_active:
                messages.error(request, "Please verify your email with OTP before logging in.")
                sociallogin.state['process'] = 'login'
                return
            
            # Link the social account to existing user
            if not sociallogin.is_existing:
                sociallogin.connect(request, existing_user)
                
        except Account.DoesNotExist:
            pass  # New user, will be created

@receiver(user_signed_up)
def set_initial_user_data(sender, request, user, sociallogin=None, **kwargs):
    """
    When user signs up via Google, set them as active and verified and send signup message
    """

    subject = "Welcome to TimestampStore!"
    message = f"Hi {user.first_name or user.email},\n\nThank you for signing up using your Google account."
    send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])

    if sociallogin:
        # Google OAuth user - automatically verified
        user.is_active = True
        user.is_verified = True
        user.save()