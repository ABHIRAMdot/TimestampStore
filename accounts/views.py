import random
from django.shortcuts import render,redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate,login,logout
from .forms import RegistrationForm, EmailOTPForm, ProfileEditForm, ChangeEmailForm, ChangePasswordForm, AddressForm
from .models import Account,Address
from django.utils import timezone
from django.db import IntegrityError
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST


# Create your views here.
def _otp_expiry_minutes():
    """
    Helper function to get OTP expiry time (default 10 minutes)
    from settings or fallback to 10.
    """
    try:
        return int(getattr(settings, 'OTP_EXPIRY_MINUTES', 2))
    except Exception:
        return 2

# convert timestamp, add timedelta, compare expiry, calculate remaining time
def is_otp_expired(otp_created_at_str):
    otp_created_at = timezone.datetime.fromisoformat(otp_created_at_str)
    expiry_time = otp_created_at + timedelta(minutes=_otp_expiry_minutes())
    return timezone.now() > expiry_time, expiry_time

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email   = form.cleaned_data['email']
            password = form.cleaned_data['password']
            phone_number = form.cleaned_data['phone_number']

            # Generate OTP (6-digit)
            otp = f"{random.randint(0, 999999):06d}"
            otp_created_at = timezone.now().isoformat()

            request.session['pending_registration'] ={
                'first_name' : first_name,
                'last_name': last_name,
                'email':email,
                'password' : password,
                'phone_number' : phone_number,
                'otp' : otp,
                'otp_created_at': otp_created_at # stored as a string in the session
            }
            request.session.set_expiry(600 ) #10 minutes
                        
            # Send OTP email
            subject = "Your account verification code"
            expiry_minutes = _otp_expiry_minutes() # calling the OTP expiring fucntion here
            message = (
                f"Hello {first_name},\n\n"
                f"Your OTP for account verification is: {otp}\n"
                f"This code will expire in {expiry_minutes} minutes.\n\n"
                "If you did not request this, please ignore this email.\n\n"
                "Thanks,\nTimestamp Team"
            )

            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
            except Exception as e:
                messages.error(request, f"Failed to send OTP email: {e}")
                return redirect('register')

            messages.success(request,"Registration successful! Please login to continue.")
            return redirect('verify_otp')
        else:
            # Display form errors from forms.py validation
            messages.error(request, "Please correct the errors below.")
    else:
        form = RegistrationForm()
    
    return render(request, 'register.html',{'form': form})
    

# OTP Verification View
@never_cache
def verify_otp(request):
    # Get pending registration data from session
    pending_data = request.session.get('pending_registration')

    if not pending_data:
        messages.error(request,"Session exired or invalid access. Please register")
        return redirect('register')

    email = pending_data.get('email')
    otp_created_at_str = pending_data.get('otp_created_at')
    stored_otp = pending_data.get('otp')

    # check if OTP has expired(USE HELPER FUNCTION HERE)
    is_expired, expiry_time = is_otp_expired(otp_created_at_str)

    #without helper function
    # if otp_created_at_str:
    #     otp_created_at  = timezone.datetime.fromisoformat(otp_created_at_str)  # this will convert the stored string in the session into datetime format for comparison
    #     expiry_time = otp_created_at + timedelta(minutes=_otp_expiry_minutes())

    #     if timezone.now() > expiry_time:
    #         messages.error(request,"OTP has expired. Please register again.")
    #         request.session.pop('pending_registration',None)
    #         return redirect('register')
        
    # calculate time remaining

    if is_expired:
        messages.error(request, "OTP has expired. Please register again.")
        request.session.pop('pending_registration', None)
        return redirect('register')


    # time_remaining = f"{_otp_expiry_minutes()} : 00"

    # if otp_created_at_str:
    #     otp_created_at = timezone.datetime.fromisoformat(otp_created_at_str)
    #     expiry_time = otp_created_at + timedelta(minutes= _otp_expiry_minutes())
    #     current_time = timezone.now()
    #     remaining = expiry_time - current_time

        # if remaining.total_seconds() >  0:
    remaining = expiry_time - timezone.now()
    minutes = int(remaining.total_seconds() // 60)
    seconds = int(remaining.total_seconds() % 60)
    time_remaining = f"{minutes} : {seconds:02d}"

    if request.method == 'POST':
        form = EmailOTPForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data['otp']

            #double check expiry on form submission (using helper function)
            is_expired,_ = is_otp_expired(otp_created_at_str)

            # if otp_created_at_str:
            #     otp_created_at = timezone.datetime.fromisoformat(otp_created_at_str)
            #     expiry_time = otp_created_at + timedelta(minutes=_otp_expiry_minutes())

                # if timezone.now() > expiry_time:
            if is_expired:
                messages.error(request, "OTP has expired. Please register again.")
                request.session.pop('pending_user_email', None)
                return redirect('register')

            if entered_otp == stored_otp :
                # OTP is correct - NOW create the user in database
                try:
                    # Check one more time if email exists (race condition prevention)
                    if Account.objects.filter(email=email).exists():
                        messages.error(request, "Email already registered. Please login")
                        request.session.pop('pending_registration')
                        return redirect('login')

                    user = Account.objects.create_user(
                        first_name = pending_data['first_name'],
                        last_name = pending_data['last_name'],
                        email = pending_data['email'],
                        password = pending_data['password']
                    )
                    user.phone_number = pending_data['phone_number']
                    user.is_active = True
                    user.is_verified = True
                    user.save()

                    #  Clean session
                    request.session.pop('pending_registration', None)
                
                    messages.success(request, "Email verified successfully! You can now log in.")
                    return redirect('login')
                except IntegrityError:
                    messages.error(request,"An error occurred. Please try again.")
                    request.session.pop('pending_registration',None)
                    return redirect('register')
            
            else:
                messages.error(request, "Invalid OTP. Please try again.")
    else:
        form = EmailOTPForm()

    return render(request, 'email/otp_verify.html', {'form': form, 'email': email, 'time_remaining':time_remaining})

@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method== 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Basic validation
        if not email or not password:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'login.html')
            
        user = authenticate(request, email=email, password=password)
        # if authentication failed
        if user is  None:
            #check the user exists but inactive
            try:
                existing_user = Account.objects.get(email=email)
                if not existing_user.is_active:
                    messages.error(request, "Your account is blocked by admin.")
                    return render(request, 'login.html')
            except Account.DoesNotExist:
                pass
            messages.error(request,'Invalid email or password.')
            return render(request, 'login.html')
        #valid user but inactive(safty check)
        if not user.is_active:
            messages.error(request, "Your account is blocked by the admin.")
            return render(request, 'login.html')

        # valid and active user login
        login(request, user)
        messages.success(request, 'Login successful! Welcome back.')


        # Send login notification email
        try:
            send_mail(
                subject='Login Notification',
                message=f'Hi {user.first_name}, you have successfully logged in.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            pass  # Don't fail login if email fails

        # Redirect to next or home
        next_url = request.GET.get('next', 'home')
        return redirect(next_url)
        # else:
        #     messages.error(request,'Invalid email or password.')
        #     return render(request, 'login.html')
    
    return render(request,'login.html',{})

@require_POST
# @never_cache
def logout_view(request):
    logout(request)
    messages.success(request,'Logged out successfully.')
    print("user logged out")
    return redirect('home')

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if not email:
            messages.error(request, "Please enter your email address.")
            return redirect('forgot_password')

        try:
            user = Account.objects.get(email=email)
        except Account.DoesNotExist:
            messages.error(request, "No account found with that email.")
            return redirect('forgot_password')

        # Generate OTP
        otp = user.generate_otp()


        subject = "Password Reset OTP - Timestamp"
        message = (
            f"Hello {user.first_name},\n\n"
            f"Your OTP for password reset is: {otp}\n"
            f"This code will expire in 10 minutes.\n\n"
            "If you didn't request this, please ignore this email.\n\n"
            "Thanks,\nTimestamp Team"
        )

        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
        request.session['reset_email'] = email
        messages.success(request, "An OTP has been sent to your email.")
        return redirect('reset_password')

    return render(request, 'password/forgot_password.html')



# Reset Password (Verify OTP + Set New Password)

def reset_password(request):

    email = request.session.get('reset_email')
    if not email:
        messages.error(request, "Session expired. Please request password reset again.")
        return redirect('forgot_password')

    try:
        user = Account.objects.get(email=email)
    except Account.DoesNotExist:
        messages.error(request, "Invalid session. Please request password reset again.")
        return redirect('forgot_password')
    
    if user.otp_created_at:
        expiry_time = user.otp_created_at + timedelta(minutes=_otp_expiry_minutes())
        if timezone.now() > expiry_time:
            messages.error(request,"OTP has expired. Please request a new one.")
            user.otp = None
            user.otp_created_at = None
            user.save()
            request.session.pop('reset_email',None)
            return redirect('forgot_password')
    
    # calculate time ramining for OTP(for the UI to show the rser time)
    time_remaining = f"{_otp_expiry_minutes()} :00"
    if user.otp_created_at:
        expiry_time = user.otp_created_at + timedelta(minutes= _otp_expiry_minutes())
        current_time = timezone.now()
        remaining =expiry_time - current_time

        if remaining.total_seconds() > 0:   # total_seconds() timedeltas default method to convert the time difference to total second as a float.
            minutes = int(remaining.total_seconds() // 60)
            seconds = int(remaining.total_seconds() % 60)
            time_remaining = f"{minutes}:{seconds:02d}"

    if request.method == 'POST':
        otp = request.POST.get('otp')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not otp or not new_password or not confirm_password:
            messages.error(request, "All fields are required.")
            return render(request,'password/reset_password.html',{'email' : email, 'time_remaining' : time_remaining})

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'password/reset_password.html',{'email': email,'time_remaining' : time_remaining})
    
        # CHECK OTP expired?
        expiry_time = user.otp_created_at + timedelta(minutes=_otp_expiry_minutes())
        if timezone.now() > expiry_time:
            messages.error(request, "OTP has expired. Please try again.")
            user.otp = None
            user.otp_created_at = None
            user.save()
            request.session.pop('reset_email',None)
            return redirect('forgot_password')
        
        # CHECK  OTP valid?
        if user.otp == otp:
            user.set_password(new_password)
            user.otp = None
            user.otp_created_at = None
            user.save()
            request.session.pop('reset_email',None)
            messages.success(request, "Password reset successful! You can now log in.")
            return redirect('login')
        else:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, 'password/reset_password.html', { 'email' : email, 'time_remaining': time_remaining})

    return render(request, 'password/reset_password.html', {'email': email, 'time_remaining': time_remaining})

# Resend OTP (During Registration)
@never_cache
def resend_otp(request):
    pending_data = request.session.get('pending_registration')

    if not pending_data:
        messages.error(request, "Session expired. Please register again.")
        return redirect('register')
    
    email = pending_data.get('email')
    first_name = pending_data.get('first_name')

    #generate New OTP
    otp = f"{random.randint(0, 999999):06d}"
    otp_created_at = timezone.now().isoformat()  #Saves the current time as a string

    #update session with new OTP
    pending_data['otp'] = otp
    pending_data['otp_created_at'] = otp_created_at
    request.session.modified = True                 # save  the modified session after changing the above

    subject = "Resend OTP - Timestamp"
    expiry_minutes = _otp_expiry_minutes()
    message = (
        f"Hello {first_name},\n\n"
        f"Your new OTP is: {otp}\n"
        f"This code will expire in {expiry_minutes} minutes.\n\n"
        "Thanks,\nTimestamp Team"
    )

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
    messages.success(request, "A new OTP has been sent to your email.")
    return redirect('verify_otp')

#resend OTP during reset password
@never_cache
def resend_reset_otp(request):
    email = request.session.get('reset_email')
    if not email:
        messages.error(request, 'Session expired. Please request password rest again.')
        return redirect('forgot_password')
    
    try:
        user = Account.objects.get(email=email)
    except Account.DoesNotExist:
        messages.error(request, "User not found. Please try again.")
        return redirect('forgot_password')
    
    #Generate new OTP
    otp = user.generate_otp()

    #send mail
    subject = "Password Reset OTP (Resent) - Timestamp"
    message = (
        f"Hello {user.first_name}, \n\n"
        f"Your new OTP for password reset is: {otp} \n"
        f"It expires in {_otp_expiry_minutes()} minutes.\n\n"
        "If you did not request this, ignore this email.\n\n"
        "Thanks,\nTimestamp Team"        
    )

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
    messages.success(request, "A new OTP has been sent to your email.")
    return redirect('reset_password')


# Profile views
@login_required
@never_cache
def profile(request):
    """Display user profile with details, addresses, and orders"""
    user = request.user
    addresses = Address.objects.filter(user=user)

    # Get orders if you have an Order model
    # orders = Order.objects.filter(user=user).order_by('-created_at')

    context = {
        'user': user,
        'addresses': addresses,
        # 'orders': orders,
    }    
    return render(request, 'accounts/profile.html',context)

@login_required
@never_cache
def edit_profile(request):
    """edit user profile details"""
    user = request.user

    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProfileEditForm(instance=user)
    
    context = {
        'form': form,
        'user': user
    }
    return render(request, 'accounts/edit_profile.html', context)

@login_required
@never_cache
def change_password(request):
    """Change user password"""
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            current_password = form.cleaned_data['current_password']
            new_password = form.cleaned_data['new_password']

            #check if current password is correct
            if not request.user.check_password(current_password):   #this check_password will check the enterd current password and the password already saved is the same
                messages.error(request, "Current password is incorrect.")
                return render(request, 'accounts/change_password.html', {'form':form})
            
            # set new password
            request.user.set_password(new_password)
            request.user.save()

            # send notification email
            try:
                send_mail(
                    subject='Password Changed Successfully',
                    message=f'Hi {request.user.first_name},\n\nYour password has been changed successfully.\n\nIf you did not make this change, please contact us immediately.\n\nThanks,\nTimestamp Team',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[request.user.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            
            messages.success(request, 'Password changed successfully! Please login again.')
            return redirect('login')
    else:
        form = ChangePasswordForm()

    return render(request, 'accounts/change_password.html', {'form': form})


@login_required
@never_cache
def change_email(request):
    """Request email change - sends OTP to new email"""
    if request.method == 'POST':
        form = ChangeEmailForm(request.POST)
        if form.is_valid():
            new_email = form.cleaned_data['new_email']

            #generate OTP
            otp = f"{random.randint(0, 999999):06d}"
            otp_created_at = timezone.now().isoformat() # changing it to standerdised string format

            #store in session
            request.session['email_change_data'] = {
                'new_email': new_email,
                'otp': otp,
                'otp_created_at': otp_created_at
            }
            request.session.set_expiry(600)   # 10 minutes

            # Send OTP email
            subject = "Email Change Verification - Timestamp"
            expiry_minutes = _otp_expiry_minutes()
            message = (
                f"Hello {request.user.first_name},\n\n"
                f"You requested to change your email address.\n"
                f"Your verification code is: {otp}\n"
                f"This code will expire in {expiry_minutes} minutes.\n\n"
                "If you did not request this, please ignore this email.\n\n"
                "Thanks,\nTimestamp Team"
            )
            
            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, 
                         [new_email], fail_silently=False)
                messages.success(request, f'Verification code sent to {new_email}')
                return redirect('verify_email_change_otp')
            except Exception as e:
                messages.error(request, f'Failed to send verification email: {e}')
    else:
        form = ChangeEmailForm()
    
    return render(request, 'accounts/change_email.html', {'form': form})


@login_required
@never_cache
def verify_email_change_otp(request):
    """Verify OTP and change email"""
    email_change_data = request.session.get('email_change_data')

    if not email_change_data:
        messages.error(request, 'Session expired. Please try again.')
        return redirect('change_email')

    new_email = email_change_data.get('new_email')
    stored_otp = email_change_data.get('otp')
    otp_created_at_str = email_change_data.get('otp_created_at')

    #check expiry
    is_expired, expiry_time = is_otp_expired(otp_created_at_str)

    if is_expired:
        messages.error(request, 'OTP has expired. Please try again.')
        requesZt.session.pop('email_change_data', None)
        return redirect('change_email')
    
    #calculating remaining time
    remaining = expiry_time - timezone.now()
    minutes = int(remaining.total_seconds() // 60)
    seconds = int(remaining.total_seconds() % 60)
    time_remaining = f"{minutes}:{seconds:02d}"

    if request.method == 'POST':
        form = EmailOTPForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data['otp']

            #double check expiry
            is_expired = is_otp_expired(otp_created_at_str)
            if is_expired:
                messages.error(request, 'OTP has expired. Please try again.')
                request.session.pop('emai_change_data', None)
                return redirect('change_email')
            
            if entered_otp == stored_otp:
                #update email
                old_email = request.user.email
                request.user.email = new_email
                request.user.save()

                # clear session
                request.session.pop('email_change_data', None)

                #send confirmation to both emails
                try:
                    #To old email
                    send_mail(
                        subject='Email Changed - Timestamp',
                        message=f'Hi {request.user.first_name},\n\nYour email has been changed from {old_email} to {new_email}.\n\nIf you did not make this change, please contact us immediately.\n\nThanks,\nTimestamp Team',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[old_email],
                        fail_silently=True,
                    )
                    # To new email
                    send_mail(
                        subject='Email Changed Successfully - Timestamp',
                        message=f'Hi {request.user.first_name},\n\nYour email has been successfully updated.\n\nThanks,\nTimestamp Team',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[new_email],
                        fail_silently=True,
                    )
                except Exception:
                    pass
                
                messages.success(request, 'Email changed successfully!')
                return redirect('profile')
            else:
                messages.error(request, 'Invalid OTP. Please try again.')
    else:
        form = EmailOTPForm()
    
    context = {
        'form': form,
        'new_email': new_email,
        'time_remaining': time_remaining
    }
    return render(request, 'accounts/verify_email_change_otp.html', context)


# Adress management views

@login_required
@never_cache
def address_list(request):
    """Display all user addresses"""
    addresses = Address.objects.filter(user=request.user)
    return render(request, 'accounts/address_list.html', {'addresses': addresses})

@login_required
@never_cache
def add_address(request):
    """Add new address"""
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, "Address added successfully!")

            # Redirect based on where user came from
            next_url = request.GET.get('next', 'address_list')
            return redirect(next_url)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AddressForm()
    return render(request, 'accounts/add_address.html', {'form': form})


@login_required
@never_cache
def edit_address(request, address_id):
    """Edit existing address"""
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=add_address)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address updated successfully!')
            return redirect('address_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AddressForm(instance=address)
    
    context = {
        'form': form,
        'address': address
    }
    return render(request, 'accounts/edit_address.html', context)


@login_required
def delete_address(request, address_id):
    """Delete address"""
    address = get_object_or_404(Address, id=address_id, user=request.user)

    if request.method == 'POST':
        address.delete()
        messages.success(request,  'Address deleted successfully!')
    
    return redirect('address_list')

@login_required
def set_default_address(request, address_id):
    """Set address as default"""
    address = get_object_or_404(Address, id=address_id, user=request.user)

    #unset all other defaults
    Address.objects.filter(user=request.user).update(is_default=False)

    # set this as default 
    address.is_default = True
    address.save()

    messages.success(request, 'Default address updated!')
    return redirect('address_list')
 