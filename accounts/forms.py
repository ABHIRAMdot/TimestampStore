from django import forms
from .models import Account
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import re

class RegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter Password',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        }),
        min_length=8,
        error_messages={
            'required': 'Password is required',
            'min_length': 'Password must be at least 8 characters long'
        }
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm Password',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        }),
        error_messages={'required': 'Please confirm your password'}
    )

    class Meta:
        model = Account
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'password']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'placeholder': 'First Name',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'last_name': forms.TextInput(attrs={
                'placeholder': 'Last Name', 
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'Enter your email',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
            'phone_number': forms.TextInput(attrs={
                'placeholder': 'Phone Number',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
        }
        error_messages = {
            'first_name': {
                'required': 'First name is required',
                'max_length': 'First name is too long'
            },
            'last_name': {
                'required': 'Last name is required', 
                'max_length': 'Last name is too long'
            },
            'email': {
                'required': 'Email is required',
                'invalid': 'Please enter a valid email address'
            },
            'phone_number': {
                'required': 'Phone number is required'
            }
        }

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        if first_name:
            if len(first_name) < 2:
                raise forms.ValidationError("First name must be at least 2 characters long")
            if not re.match(r'^[A-Za-z\s]+$', first_name):
                raise forms.ValidationError("First name can only contain letters and spaces")
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name')
        if last_name:
            if len(last_name) < 2:
                raise forms.ValidationError("Last name must be at least 2 characters long")
            if not re.match(r'^[A-Za-z\s]+$', last_name):
                raise forms.ValidationError("Last name can only contain letters and spaces")
        return last_name

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            try:
                validate_email(email)
            except ValidationError:
                raise forms.ValidationError("Please enter a valid email address")
            
            # if Account.objects.filter(email=email).exists():
                # raise forms.ValidationError("This email is already registered. Please use a different email.")
        return email
    
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
    
        if not phone_number:
            return phone_number
    
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone_number)
    
        # Must be exactly 10 digits
        if len(digits_only) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits.")
    
        # Check for all same digit (1111111111, 2222222222, etc.)
        if len(set(digits_only)) == 1:
            raise forms.ValidationError("Please enter a valid phone number.")
    
        # Check for sequential numbers (1234567890, 9876543210, etc.)
        sequential_patterns = [
            '1234567890',
            '0123456789', 
            '9876543210',
            '0987654321'
        ]
    
        if digits_only in sequential_patterns:
            raise forms.ValidationError("Please enter a valid phone number.")
    
        # Check if phone number already exists
        if Account.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError("This phone number is already registered.")
    
        return phone_number

    

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            if len(password) < 8:
                raise forms.ValidationError("Password must be at least 8 characters long")
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
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match. Please make sure both passwords are the same.")
        
        return cleaned_data
    
# OTP verification form
class EmailOTPForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter OTP',
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent tracking-widest text-center'
        }),
        error_messages={
            'required': 'Please enter the OTP sent to your email.',
            'min_length': 'OTP must be 6 digits.',
            'max_length': 'OTP must be 6 digits.'
        }
    )