from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.text import slugify
from category.models import Category, Offer
# from offers.models import Offer
# Create your views here.

# Offer Management Views

@login_required(login_url='admin_login')
def offer_list(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_login')

    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    offers = Offer.objects.all().select_related('category').order_by('-created_at')

    if search_query:
        offers = offers.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if status_filter:
        offers = offers.filter(status=status_filter)

    paginator = Paginator(offers, 10)
    page_number = request.GET.get('page')
    offers_page = paginator.get_page(page_number)

    context = {
        'offers': offers_page,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'offer_list.html', context)


@login_required(login_url='admin_login')
def add_offer(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_login')
    
    categories = Category.objects.filter(is_listed=True).order_by('category_name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        discount = request.POST.get('discount', '').strip()
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        status = request.POST.get('status', 'active')
        description = request.POST.get('description', '').strip()

        # Validation
        if not name or not category_id or not discount or not start_date or not end_date:
            messages.error(request, 'All required fields must be filled.')
            return render(request, 'add_offer.html', {'categories': categories})
        
        try:
            discount = float(discount)
            if discount <= 0 or discount > 100:
                raise ValueError
        except ValueError:
            messages.error(request, 'Discount must be between 0 and 100.')
            return render(request, 'add_offer.html', {'categories': categories})

        # Create offer
        Offer.objects.create(
            name=name,
            category_id=category_id,
            discount=discount,
            start_date=start_date,
            end_date=end_date,
            status=status,
            description=description
        )

        messages.success(request, f'Offer "{name}" created successfully.')
        return redirect('offer_list')
    
    context = {
        'categories': categories,
    }
    return render(request, 'add_offer.html', context)


@login_required(login_url='admin_login')
def edit_offer(request, offer_id):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_login')
    
    offer = get_object_or_404(Offer, id=offer_id)
    categories = Category.objects.filter(is_listed=True).order_by('category_name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        discount = request.POST.get('discount', '').strip()
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        status = request.POST.get('status', 'active')
        description = request.POST.get('description', '').strip()

        # Validation
        if not name or not category_id or not discount or not start_date or not end_date:
            messages.error(request, 'All required fields must be filled.')
            return render(request, 'edit_offer.html', {
                'offer': offer,
                'categories': categories,
            })
        
        try:
            discount = float(discount)
            if discount <= 0 or discount > 100:
                raise ValueError
        except ValueError:
            messages.error(request, 'Discount must be between 0 and 100.')
            return render(request, 'edit_offer.html', {
                'offer': offer,
                'categories': categories,
            })

        # Update offer
        offer.name = name
        offer.category_id = category_id
        offer.discount = discount
        offer.start_date = start_date
        offer.end_date = end_date
        offer.status = status
        offer.description = description
        offer.save()

        messages.success(request, f'Offer "{name}" updated successfully.')
        return redirect('offer_list')
    
    context = {
        'offer': offer,
        'categories': categories,
    }
    return render(request, 'edit_offer.html', context)


@login_required(login_url='admin_login')
def delete_offer(request, offer_id):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('admin_login')
    
    offer = get_object_or_404(Offer, id=offer_id)
    offer_name = offer.name
    offer.delete()
    
    messages.success(request, f'Offer "{offer_name}" deleted successfully.')
    return redirect('offer_list')
