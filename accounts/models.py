from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils import timezone
from datetime import timedelta
import random
import string

# Create your models here.


class MyAccountManager(BaseUserManager):
    def create_user(self, first_name, last_name, email, password=None):
        if not email:
            raise ValueError("user must have an email address")

        user = self.model(
            email=self.normalize_email(
                email
            ),  # means if you enter capital emails it will change it to small letters
            first_name=first_name,
            last_name=last_name,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, first_name, last_name, email, password):
        user = self.create_user(
            email=self.normalize_email(email),
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        user.is_admin = True
        user.is_active = True
        user.is_staff = True
        user.is_superadmin = True
        user.is_superuser = True
        user.is_verified = True

        user.save(using=self._db)

        return user

    def cleanup_expired(self, expiry_minutes=10):
        """Delete unverified accounts whose OTP expired."""
        expiry_time = timezone.now() - timedelta(minutes=expiry_minutes)
        expired_users = self.filter(
            is_active=False, is_verified=False, otp_created_at__lt=expiry_time
        )
        count = expired_users.count()
        expired_users.delete()
        return count


class Account(AbstractBaseUser):  # account model
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    profile_image = models.ImageField(
        upload_to="profile_images/", blank=True, null=True
    )

    otp = models.CharField(max_length=6, blank=True, null=True)  # for emai Otp
    otp_created_at = models.DateTimeField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)  # user must verify OTP once

    referral_code = models.CharField(
        max_length=12,
        unique=True,
        blank=True,
        null=True,
        help_text="Unique referral code for this user",
    )

    referred_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals",
        help_text="User who referred this account.",
    )

    # Permissions
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_superadmin = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = MyAccountManager()

    def __str__(self):
        return self.email  # to return email when getting the details

    # for allauth to desplay username(default) change to email internally
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def has_perm(self, perm, obj=None):
        return (
            self.is_admin
        )  # if the user is an admin then he has all the permission to do the works ( for django admin site only)

    def has_module_perms(self, app_label):
        return True

    def generate_otp(self):
        self.otp = "".join(random.choices(string.digits, k=6))
        self.otp_created_at = timezone.now()
        self.save()
        return self.otp

    def generate_referral_code(self):
        """
        Generate unique referral code for user.
        Format: FIRSTNAME + 6 random chars (e.g., JOHN-A7B9C2)
        """

        if self.referral_code:
            return self.referral_code  # already has code
        # firstname + random characters
        base = self.first_name.upper()[:4].ljust(4, "X")

        # keep generarting until unique
        while True:
            random_part = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=6)
            )
            code = f"{base}{random_part}"

            # check if code already exists
            if not Account.objects.filter(referral_code=code).exists():
                self.referral_code = code
                self.save()
                return code

    def save(self, *args, **kwargs):
        """
        Override save to auto-generate referral code.

        WHY OVERRIDE SAVE?
        - Ensures every verified user has referral code
        - No need to remember to call generate_referral_code()
        - Automatic and consistent
        """
        # Generate referral code for verified users without one
        if self.is_verified and not self.referral_code:
            self.generate_referral_code()

        super().save(*args, **kwargs)


class Address(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="address")
    full_name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15)
    second_mobile = models.CharField(max_length=15, null=True, blank=True)
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Addresses"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.full_name}, {self.city}"

    def save(self, *args, **kwargs):
        # If this is set as default, unset other defaults for this user
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).update(
                is_default=False
            )
        super().save(*args, **kwargs)
