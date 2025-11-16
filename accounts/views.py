import random
from django.shortcuts import render,redirect
from django.contrib import messages
from django.contrib.auth import authenticate,login,logout
from .forms import RegistrationForm, EmailOTPForm
from .models import Account
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
                'phone_number' : password,
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

    email = request.session.get('email')
    otp_created_at_str = pending_data.get('otp_created_at')
    stored_otp = pending_data.get('otp')

    # check if OTP has expired    
    if otp_created_at_str:
        otp_created_at  = timezone.datetime.fromisoformat(otp_created_at_str)  # this will convert the stored string in the session into datetime format for comparison
        expiry_time = otp_created_at + timedelta(minutes=_otp_expiry_minutes())

        if timezone.now() > expiry_time:
            messages.error(request,"OTP has expired. Please register again.")
            request.session.pop('pending_registration',None)
            return redirect('register')
        
    # calculate time remaining
    time_remaining = f"{_otp_expiry_minutes()} : 00"

    if otp_created_at_str:
        otp_created_at = timezone.datetime.fromisoformat(otp_created_at_str)
        expiry_time = otp_created_at + timedelta(minutes= _otp_expiry_minutes())
        current_time = timezone.now()
        remaining = expiry_time - current_time

        if remaining.total_seconds() >  0:
            minutes = int(remaining.total_seconds() // 60)
            seconds = int(remaining.total_seconds() % 60)
            time_remaining = f"{minutes} : {seconds:02d}"

    if request.method == 'POST':
        form = EmailOTPForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data['otp']

            #double check expiry on form submission
            if otp_created_at_str:
                otp_created_at = timezone.datetime.fromisoformat(otp_created_at_str)
                expiry_time = otp_created_at + timedelta(minutes=_otp_expiry_minutes())

                if timezone.now() > expiry_time:
                    messages.error(request, "OTP has expired. Please register again.")
                    request.session.pop('pending_user_email', None)
                    return redirect('register')
            
            if stored_otp == entered_otp:
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
                    request.session.modified = True  # Force session save
                
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
            messages.success(request,'Invalid email or password.')
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
        otp = f"{random.randint(0, 999999):06d}"
        user.otp = otp
        user.otp_created_at = timezone.now()
        user.save()

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
    
    # calculate time ramining for OTP
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
            return redirect('password/reset_password.html',{'email': email,'time_remaining' : time_remaining})
    
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
    otp = f"{random.randint(0, 999999):06d}"
    user.otp = otp
    user.otp_created_at = timezone.now()
    user.save()

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