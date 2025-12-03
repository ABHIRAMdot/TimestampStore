from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .invoice import generate_invoice_pdf
from django.views.decorators.csrf import csrf_protect

from .models import Order, OrderItem, OrderStatusHistory
from .forms import AdminOrderStatusForm, OrderSearchForm
from .utils import (
    update_order_status, 
    search_orders, 
    filter_orders,
    get_order_statistics,
    check_and_update_order_status_after_item_change,
)
from products.models import Product_varients


def admin_required(view_func):
    """Decorator to check if user is admin"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to continue.')
            return redirect('admin_login')
        if not request.user.is_superadmin:
            messages.error(request, 'Access denied. Admin privilages required.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


@admin_required
def admin_orders_list(request):
    """Admin view: List all orders with search, filter, sort"""
    orders = Order.objects.select_related('user','shipping_address').prefetch_related('items').order_by('-created_at')

    form=OrderSearchForm(request.GET)

    if form.is_valid():
        search_query =form.cleaned_data.get('search', '').strip()
        if search_query:
            orders = search_orders(orders, search_query)

        filters = {
            'status': form.cleaned_data.get('status'),
            'payment_method': form.cleaned_data.get('payment_method'),
            'date_from': form.cleaned_data.get('date_from'),
            'date_to': form.cleaned_data.get('date_to'),
        }
        orders = filter_orders(orders, filters)

        sort_by = form.cleaned_data.get('sort_by') or '-created_at'
        orders = orders.order_by(sort_by)
    
    paginator = Paginator(orders, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    stats = get_order_statistics()

    context = {
        'page_obj': page_obj,
        'form':form,
        'stats': stats,
        'total_count': orders.count(),
    }
    return render(request, 'admin/orders/order_list.html', context)



@csrf_protect
@admin_required
def admin_order_detail(request, order_id):
    """Admin view: Detailed view of order with status update"""
    
    order = get_object_or_404(
        Order.objects.select_related('user', 'shipping_address', 'cancelled_by')
        .prefetch_related('items__product', 'items__variant', 'status_history__changed_by'),
        order_id=order_id
    )
    
    if request.method == 'POST':
        form = AdminOrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            new_status = form.cleaned_data['status']
            notes = form.cleaned_data.get('notes', '')
            tracking = form.cleaned_data.get('tracking_number')
            
            success, message = update_order_status(order, new_status, changed_by=request.user, notes=notes)
            
            if success:
                if tracking:
                    order.tracking_number = tracking
                    order.save()
                messages.success(request, message)
            else:
                messages.error(request, message)
            
            return redirect('admin_order_detail', order_id=order.order_id)
    else:
        form = AdminOrderStatusForm(instance=order)
    
    context = {
        'order': order,
        'form': form,
    }
    
    return render(request, 'admin/orders/order_detail.html', context)


@admin_required
@require_POST
def admin_approve_return(request, item_id):
    """Admin: Approve return request"""
    
    item = get_object_or_404(OrderItem, id=item_id)
    
    if item.status != 'return_requested':
        messages.error(request, "No return request found for this item.")
        return redirect('admin_order_detail', order_id=item.order.order_id)
    
    #Approve return (this restores stock automatically)
    success, message = item.approve_return()
    
    if success:
        #Create status history
        OrderStatusHistory.objects.create(
            order=item.order,
            old_status=item.order.status,
            new_status=item.order.status,
            changed_by=request.user,
            notes=f"Return approved for item: {item.product_name} ({item.variant_colour})"
        )
        messages.success(request, message)
    else:
        messages.error(request, message)
    
    # Redirect based on where request came from
    next_url = request.POST.get('next', 'admin_order_detail')
    if next_url == 'return_requests_list':
        return redirect('admin_return_requests_list')
    else:
        return redirect('admin_order_detail', order_id=item.order.order_id)


@admin_required
def admin_inventory_management(request):
    """Admin view: Inventory/Stock management"""
    
    stock_filter = request.GET.get('filter', 'all')
    search_query = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort', 'product__product_name')
    
    variants = Product_varients.objects.select_related(
        'product', 'product__category'
    ).filter(
        is_listed=True,
        product__is_listed=True
    )
    
    if search_query:
        variants = variants.filter(
            Q(product__product_name__icontains=search_query) |
            Q(colour__icontains=search_query) |
            Q(product__category__category_name__icontains=search_query)
        )
    
    if stock_filter == 'out_of_stock':
        variants = variants.filter(stock=0)
    elif stock_filter == 'low_stock':
        variants = variants.filter(stock__lte=10, stock__gt=0)
    elif stock_filter == 'in_stock':
        variants = variants.filter(stock__gt=10)
    
    valid_sorts = [
        'product__product_name', '-product__product_name',
        'stock', '-stock',
        'colour', '-colour',
        'price', '-price'
    ]
    if sort_by in valid_sorts:
        variants = variants.order_by(sort_by)
    else:
        variants = variants.order_by('product__product_name')
    
    paginator = Paginator(variants, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    total_variants = Product_varients.objects.filter(
        is_listed=True, product__is_listed=True
    ).count()
    out_of_stock_count = Product_varients.objects.filter(
        is_listed=True, product__is_listed=True, stock=0
    ).count()
    low_stock_count = Product_varients.objects.filter(
        is_listed=True, product__is_listed=True, stock__lte=10, stock__gt=0
    ).count()
    
    context = {
        'page_obj': page_obj,
        'stock_filter': stock_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'total_variants': total_variants,
        'out_of_stock_count': out_of_stock_count,
        'low_stock_count': low_stock_count,
    }
    
    return render(request, 'admin/orders/inventory.html', context)


@admin_required
@require_POST
def admin_update_stock(request, variant_id):
    """Admin: Update stock for a variant (AJAX)"""
    
    variant = get_object_or_404(Product_varients, id=variant_id)
    
    try:
        new_stock = int(request.POST.get('stock', 0))
        
        if new_stock < 0:
            return JsonResponse({
                'success': False,
                'message': 'Stock cannot be negative'
            })
        
        old_stock = variant.stock
        variant.stock = new_stock
        variant.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Stock updated from {old_stock} to {new_stock}',
            'new_stock': new_stock
        })
    
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid stock value'
        })
    
@admin_required
def admin_return_requests_list(request):
    """Admin view: List all pending return requests"""

    #Get all items with return_requested status
    return_requests =OrderItem.objects.filter(status='return_requested').select_related('order__user', 'product', 'variant').order_by('return_requested_at')

    #SEarch fuctionality
    search_query = request.GET.get('search', '').strip()
    if search_query:
        return_requests = return_requests.filter(
            Q(order__order_id__icontains=search_query) |
            Q(product_name__icontains=search_query) |
            Q(order__user__email__icontains=search_query)
        )

    #pagination
    paginator = Paginator(return_requests, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'total_pending': return_requests.count(),
    }

    return render(request, 'admin/orders/return_requests_list.html', context)


@admin_required
@require_POST
def admin_reject_return(request, item_id):
    """Admin: Reject return request"""
    
    item = get_object_or_404(OrderItem, id=item_id)
    
    if item.status != 'return_requested':
        messages.error(request, "No return request found for this item.")
        return redirect('admin_order_detail', order_id=item.order.order_id)
    
    rejection_reason = request.POST.get('rejection_reason', '').strip()
    
    if not rejection_reason:
        messages.error(request, "Please provide a rejection reason.")
        return redirect('admin_order_detail', order_id=item.order.order_id)
    
    # Update item status back to delivered
    item.status = 'delivered'
    item.return_reason = f"REJECTED: {rejection_reason}"  # Store rejection reason
    item.save()
    
    # Create status history
    OrderStatusHistory.objects.create(
        order=item.order,
        old_status=item.order.status,
        new_status=item.order.status,
        changed_by=request.user,
        notes=f"Return rejected for item: {item.product_name}. Reason: {rejection_reason}"
    )
    
    messages.warning(request, f"Return request rejected: {rejection_reason}")
    
    # Redirect based on where request came from
    next_url = request.POST.get('next', 'admin_order_detail')
    if next_url == 'return_requests_list':
        return redirect('admin_return_requests_list')
    else:
        return redirect('admin_order_detail', order_id=item.order.order_id)
    
@admin_required
def admin_download_invoice(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)

    if order.status in ['pending', 'cancelled']:
        messages.error(request, "Invoice not available for this order.")
        return redirect('admin_order_detail', order_id=order.order_id)    
    return generate_invoice_pdf(order)
