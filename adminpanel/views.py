from django.shortcuts import render, redirect, get_object_or_404
from accounts.models import Account
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.utils.text import slugify
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST



# Create your views here.
@never_cache
def admin_login(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            print("admin login authentication")
            return redirect('admin_dashboard')
        
        else:
            logout(request) #logout non-admin
            print("logout non admin")
            return render(request,'admin_login.html')
    
    if request.method == 'POST':
        print("methode is POST")
        email = request.POST.get('email')
        password = request.POST.get('password')

        if not email or not password:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'admin_login.html')     

        user = authenticate(request, email=email, password=password) 

        if user is not None:
            if user.is_superuser:
                login(request,user)
                messages.success(request,'Login successful! Welcome back.')
                return redirect('admin_dashboard')
            else:
                messages.error(request, "You don't have the admin previlages.")
                return render(request,'admin_login.html')
        else:
            messages.error(request,'Invalid email or password.')
            return render(request, 'admin_login.html')   
    print("Hiiiii")         
    return render(request, 'admin_login.html')



@login_required(login_url='admin_login')
@never_cache
def admin_dashboard(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_login')
    
    total_users =  Account.objects.filter(is_superuser=False).count()
    active_users = Account.objects.filter(is_superuser=False, is_active = True).count()
    blocked_users = Account.objects.filter(is_superuser=False, is_active=False).count()

    context = {
        'total_users' : total_users,
        'active_users' : active_users,
        'blocked_users' : blocked_users,
    }
    return render(request, 'admin_dashboard.html',context)


@login_required(login_url='admin_login')
def user_list(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_login')

    search_query = request.GET.get('search','')

    #get all users excluding superusers
    users = Account.objects.filter(is_superuser=False).order_by('-date_joined')

    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query)|
            Q(last_name__icontains=search_query)|
            Q(email__icontains=search_query)|
            Q(phone_number__icontains=search_query)
        )        

    paginator = Paginator(users,10) # 10 users per page
    page_number = request.GET.get('page')
    users_page = paginator.get_page(page_number) #paginator method

    context = {
        'users':users_page,
        'search_query' : search_query,
    }
    return render(request,'user_list.html',context)

# Block/Unblock User
@login_required(login_url='admin_login')
def toggle_user_status(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('admin_login')

    user = get_object_or_404(Account,id=user_id, is_superuser=False)

    if user.is_active:
        user.is_active = False
        messages.success(request,f'User {user.email} has been blocked successfully.')
    else:
        user.is_active = True
        messages.success(request,f'User {user.email} has been unblocked successfully.')

    user.save()
    return redirect('user_list')

@login_required(login_url='admin_login')
@require_POST
@never_cache
def admin_logout(request):
    logout(request)
    messages.success(request,"You have been logged out successfuly.")
    return redirect('admin_login')        


