from django import forms
from .models import Account, Address
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import re


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Enter Password",
                "class": "w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
            }
        ),
        min_length=8,
        error_messages={
            "required": "Password is required",
            "min_length": "Password must be at least 8 characters long",
        },
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Confirm Password",
                "class": "w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
            }
        ),
        error_messages={"required": "Please confirm your password"},
    )

    # referral_code = forms.CharField(max_length=12, required=False,
    #                                 widget=forms.TextInput(attrs={
    #                                     'placeholder': 'Referral code (optional.)',
    #                                     'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'

    #                                 }))

    class Meta:
        model = Account
        fields = ["first_name", "last_name", "email", "phone_number", "password"]
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "placeholder": "First Name",
                    "class": "w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "placeholder": "Last Name",
                    "class": "w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "Enter your email",
                    "class": "w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "placeholder": "Phone Number",
                    "class": "w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
                }
            ),
        }
        error_messages = {
            "first_name": {
                "required": "First name is required",
                "max_length": "First name is too long",
            },
            "last_name": {
                "required": "Last name is required",
                "max_length": "Last name is too long",
            },
            "email": {
                "required": "Email is required",
                "invalid": "Please enter a valid email address",
            },
            "phone_number": {"required": "Phone number is required"},
        }

    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name").strip()
        if first_name:
            if len(first_name) < 2:
                raise forms.ValidationError(
                    "First name must be at least 2 characters long"
                )
            if not re.match(r"^[A-Za-z\s]+$", first_name):
                raise forms.ValidationError(
                    "First name can only contain letters and spaces"
                )
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get("last_name").strip()
        if last_name:
            if len(last_name) < 2:
                raise forms.ValidationError(
                    "Last name must be at least 2 characters long"
                )
            if not re.match(r"^[A-Za-z\s]+$", last_name):
                raise forms.ValidationError(
                    "Last name can only contain letters and spaces"
                )
        return last_name

    def clean_email(self):
        email = self.cleaned_data.get("email").strip()
        if email:
            try:
                validate_email(email)
            except ValidationError:
                raise forms.ValidationError("Please enter a valid email address")

            # if Account.objects.filter(email=email).exists():
            # raise forms.ValidationError("This email is already registered. Please use a different email.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number")

        if not phone_number:
            return phone_number

        # Remove all non-digit characters
        digits_only = re.sub(r"\D", "", phone_number)

        # Must be exactly 10 digits
        if len(digits_only) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits.")

        # Check for all same digit (1111111111, 2222222222, etc.)
        if len(set(digits_only)) == 1:
            raise forms.ValidationError("Please enter a valid phone number.")

        # Check for sequential numbers (1234567890, 9876543210, etc.)
        sequential_patterns = ["1234567890", "0123456789", "9876543210", "0987654321"]

        if digits_only in sequential_patterns:
            raise forms.ValidationError("Please enter a valid phone number.")

        # Check if phone number already exists
        if Account.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError("This phone number is already registered.")

        return phone_number

    # def clean_referral_code(self):
    #     code = self.cleaned_data.get('referral_code', '').strip()

    #     if code:
    #         if not Account.objects.filter(referral_code=code).exists():
    #             raise forms.ValidationError("Invalid referral code.")

    #     return code

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            if len(password) < 8:
                raise forms.ValidationError(
                    "Password must be at least 8 characters long"
                )
            # Add more password strength checks if needed
            # if not re.search(r'[A-Z]', password):
            #     raise forms.ValidationError("Password must contain at least one uppercase letter")
            # if not re.search(r'[a-z]', password):
            #     raise forms.ValidationError("Password must contain at least one lowercase letter")
            # if not re.search(r'[0-9]', password):
            #     raise forms.ValidationError("Password must contain at least one number")
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError(
                "Passwords do not match. Please make sure both passwords are the same."
            )

        return cleaned_data


# OTP verification form
class EmailOTPForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter OTP",
                "class": "w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent tracking-widest text-center",
            }
        ),
        error_messages={
            "required": "Please enter the OTP sent to your email.",
            "min_length": "OTP must be 6 digits.",
            "max_length": "OTP must be 6 digits.",
        },
    )


# profile form
class ProfileEditForm(forms.ModelForm):
    """Form for editing user profile (excluding email)"""

    class Meta:
        model = Account
        fields = ["first_name", "last_name", "phone_number", "profile_image"]
        widget = {
            "first_name": forms.TextInput(
                attrs={
                    "placeholder": "Phone Number",
                    "class": "form-control",
                }
            ),
            "last_name": forms.TextInput(
                attrs={"placeholder": "Last Name", "class": "form-control"}
            ),
            "phone_number": forms.TextInput(
                attrs={"placeholder": "Phone Number", "class": "form-control"}
            ),
            "profile_image": forms.FileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
        }

        def clean_first_name(self):
            first_name = self.cleaned_data.get("first_name", "").strip()
            if first_name:
                if len(first_name) < 2:
                    raise forms.ValidationError(
                        "First name must be at least 2 characters long"
                    )
                if not re.match(r"^[A-Za-z\s]+$", first_name):
                    raise forms.ValidationError(
                        "First name can only contain letters and spaces"
                    )
            return first_name

        def clean_last_name(self):
            last_name = self.cleaned_data.get("last_name", "").strip()
            if last_name:
                if len(last_name) < 2:
                    raise forms.ValidationError(
                        "Last name must be at least 2 characters long"
                    )
                if not re.match(r"^[A-Za-z\s]+$", last_name):
                    raise forms.ValidationError(
                        "Last name can only contain letters and spaces"
                    )
            return last_name

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number")

        if not phone_number:
            return phone_number

        # Remove all non-digit characters
        digits_only = re.sub(r"\D", "", phone_number)

        # Must be exactly 10 digits
        if len(digits_only) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits.")

        # Check for all same digit
        if len(set(digits_only)) == 1:
            raise forms.ValidationError("Please enter a valid phone number.")

        # Check for sequential numbers
        sequential_patterns = ["1234567890", "0123456789", "9876543210", "0987654321"]
        if digits_only in sequential_patterns:
            raise forms.ValidationError("Please enter a valid phone number.")

        # Check if phone number already exists (excluding current user)
        if self.instance:
            existing = Account.objects.filter(phone_number=phone_number).exclude(
                pk=self.instance.pk
            )
            if existing.exists():
                raise forms.ValidationError("This phone number is already registered.")

        return phone_number

    def clean_profile_image(self):
        profile_image = self.cleaned_data.get("profile_image")

        if profile_image:
            # check file size (limit to 5MB)
            if profile_image.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image file size cannot exceed 5MB.")

            # check file type
            valid_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
            ext = profile_image.name.split(".")[-1].lower()
            if ext not in valid_extensions:
                raise ValidationError(
                    "Only JPG, JPEG, PNG, GIF, and WEBP images are allowed."
                )

        return profile_image


# not a model form
class ChangePasswordForm(forms.Form):
    """Form for changing user password"""

    current_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Current Password"}
        ),
        label="Current Password",
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "New Password"}
        ),
        label="New Password",
        min_length=8,
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm New Password"}
        ),
        label="Confirm Password",
    )

    def clean_new_password(self):
        new_password = self.cleaned_data.get("new_password")
        if new_password and len(new_password) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long")
        return new_password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError("New passwords do not match.")

        return cleaned_data


# not a model form
class ChangeEmailForm(forms.Form):
    """Form for requesting email change"""

    new_email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "New Email Address"}
        ),
        label="New Email Address",
    )

    def clean_new_email(self):
        email = self.cleaned_data.get("new_email", "").strip()

        if email:
            try:
                validate_email(email)
            except ValidationError:
                raise forms.ValidationError("Please enter a valid email address")

            # Check if email already exists
            if Account.objects.filter(email=email).exists():
                raise forms.ValidationError("This email is already registered.")

        return email


# adress form(model form)
class AddressForm(forms.ModelForm):
    """Form for adding/editing addresses"""

    class Meta:
        model = Address
        fields = [
            "full_name",
            "mobile",
            "second_mobile",
            "street_address",
            "city",
            "state",
            "postal_code",
            "is_default",
        ]
        widgets = {
            "full_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Full Name"}
            ),
            "mobile": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Mobile Number"}
            ),
            "second_mobile": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Alternate Mobile (Optional)",
                }
            ),
            "street_address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "House No., Building Name, Street, Area",
                    "rows": 3,
                }
            ),
            "city": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "City"}
            ),
            "state": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "State"}
            ),
            "postal_code": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Postal Code"}
            ),
            "is_default": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_full_name(self):
        full_name = self.cleaned_data.get("full_name", "").strip()
        if full_name:
            if len(full_name) < 3:
                raise forms.ValidationError(
                    "Full name must be at least 3 characters long"
                )
            if not re.match(r"^[A-Za-z\s]+$", full_name):
                raise forms.ValidationError(
                    "Full name can only contain letters and spaces"
                )
        return full_name

    def clean_mobile(self):
        mobile = self.cleaned_data.get("mobile")

        if not mobile:
            raise forms.ValidationError("Mobile number is required")

        # Remove all non-digit characters
        digits_only = re.sub(r"\D", "", mobile)

        # Must be exactly 10 digits
        if len(digits_only) != 10:
            raise forms.ValidationError("Mobile number must be exactly 10 digits.")

        # Check for all same digit
        if len(set(digits_only)) == 1:
            raise forms.ValidationError("Please enter a valid mobile number.")

        # Check for sequential numbers
        sequential_patterns = ["1234567890", "0123456789", "9876543210", "0987654321"]
        if digits_only in sequential_patterns:
            raise forms.ValidationError("Please enter a valid mobile number.")

        return mobile

    def clean_second_mobile(self):
        second_mobile = self.cleaned_data.get("second_mobile")

        if second_mobile:
            # Remove all non-digit characters
            digits_only = re.sub(r"\D", "", second_mobile)

            # Must be exactly 10 digits
            if len(digits_only) != 10:
                raise forms.ValidationError("Mobile number must be exactly 10 digits.")

            # Check for all same digit
            if len(set(digits_only)) == 1:
                raise forms.ValidationError("Please enter a valid mobile number.")

            # Check for sequential numbers
            sequential_patterns = [
                "1234567890",
                "0123456789",
                "9876543210",
                "0987654321",
            ]
            if digits_only in sequential_patterns:
                raise forms.ValidationError("Please enter a valid mobile number.")

            # Check if same as primary mobile
            primary_mobile = self.cleaned_data.get("mobile")
            if primary_mobile and second_mobile == primary_mobile:
                raise forms.ValidationError(
                    "Alternate mobile cannot be same as primary mobile."
                )

        return second_mobile

    def clean_postal_code(self):
        postal_code = self.cleaned_data.get("postal_code", "").strip()

        if postal_code:
            # Remove all non-digit characters
            digits_only = re.sub(r"\D", "", postal_code)

            # Must be exactly 6 digits for Indian PIN codes
            if len(digits_only) != 6:
                raise forms.ValidationError("Postal code must be exactly 6 digits.")

            # Check if all digits are same
            if len(set(digits_only)) == 1:
                raise forms.ValidationError("Please enter a valid postal code.")

        return postal_code

    def clean_city(self):
        city = self.cleaned_data.get("city", "").strip()
        if city:
            if len(city) < 2:
                raise forms.ValidationError(
                    "City name must be at least 2 characters long"
                )
            if not re.match(r"^[A-Za-z\s]+$", city):
                raise forms.ValidationError(
                    "City name can only contain letters and spaces"
                )
        return city

    def clean_state(self):
        state = self.cleaned_data.get("state", "").strip()
        if state:
            if len(state) < 2:
                raise forms.ValidationError(
                    "State name must be at least 2 characters long"
                )
            if not re.match(r"^[A-Za-z\s]+$", state):
                raise forms.ValidationError(
                    "State name can only contain letters and spaces"
                )
        return state
