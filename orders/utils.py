from decimal import Decimal
from django.db.models import Q
from .models import Order, OrderItem, OrderStatusHistory
from django.utils import timezone
from wallet.utils import credit_wallet
from coupons.models import CouponUsage



def create_order_form_cart(user, cart, shipping_address, payment_method):
    """Create an order from cart items
    Returns: (order, error_message)
    """
    try:
        #validate cart
        if not cart.items.exists():
            return None, "Cart is empty"
        
        #restrict cod above 10,000
        if payment_method == 'cod':
            payable_amount = cart.get_total_amount()

            if payable_amount > Decimal('10000'):
                return None, "Cash on Delivery is not available for orders above ₹10,000"
        
        #create order
        order = Order.objects.create(
            user=user,
            shipping_address=shipping_address,
            full_name=shipping_address.full_name,
            mobile=shipping_address.mobile,
            street_address=shipping_address.street_address,
            city=shipping_address.city,
            state=shipping_address.state,
            postal_code=shipping_address.postal_code,
            payment_method=payment_method,
            subtotal=Decimal('0.00'),
            total_amount=Decimal('0.00')
        )

        #Create order items from cart
        for cart_item in cart.items.all():
            #Double check availability
            if not cart_item.is_product_available():
                order.delete()
                return None, f"{cart_item.product.product_name} is no longer available"
            
            #Check stock
            if cart_item.quantity > cart_item.variant.stock:
                order.delete()
                return None, f"Insufficient stock for {cart_item.product.product_name}"
            
            #Calculate pricing
            original_price = cart_item.variant.price
            current_price =cart_item.price
            discount = original_price - current_price

            #Create order Item
            order_item = OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                variant=cart_item.variant,
                product_name=cart_item.product.product_name,
                variant_colour=cart_item.variant.colour,
                price=current_price,
                original_price=original_price,
                discount_amount=discount,
                quantity=cart_item.quantity,
                status='pending'
            )

            #Reduce stock
            cart_item.variant.stock -= cart_item.quantity
            cart_item.variant.save()
        
        #calculate totals
        order.calculate_totals()

        #Clear cart
        cart.items.all().delete()
        cart.total = Decimal('0.00')
        cart.save()

        return order, None
    
    except Exception as e:
        return None, str(e)

def cancel_order(order, reason=None, cancelled_by=None):
    """
    Cancel entire order and restore stock
    Returns: (success, message)
    """
    if not order.can_be_cancelled:
        return False, "This order cannot be cancelled"
    
    # refund_amount = order.total_refund_amount # property that already written in Orde model

    #cancel all items
    for item in order.items.all():
        if item.can_be_cancelled:
            #Restore stock
            item.variant.stock += item.quantity
            item.variant.save()

            item.status = 'cancelled'
            item.cancellation_reason = reason
            item.cancelled_at = timezone.now()
            item.save()

    refund_amount = order.total_refund_amount

    # Upadate order
    old_status = order.status
    order.status = 'cancelled'
    order.cancellation_reason = reason
    order.cancelled_by = cancelled_by
    order.cancelled_at = timezone.now()
    if refund_amount > 0:
        order.payment_status = 'refunded'
    else:
        order.payment_status = 'pending'
        
    order.save()

    # Record status change
    OrderStatusHistory.objects.create(
        order=order,
        old_status=old_status,
        new_status='cancelled',
        changed_by=cancelled_by,
        notes=reason
    )


    #if the whole order is cancelled, refund everything
    if refund_amount > 0:
        description = f"Refund for cancelled order {order.order_id}"
        credit_wallet(
            user=order.user,
            amount=refund_amount,
            tx_type='credit',
            description=description,
            order=order,
        )

    return True, "Order cancelled successfully"

def validate_status_transition(current_status, new_staus):
    """
    Validate if status transition is allowed (step-by-step progression)
    Returns: (is_valid, error_message)
    """
    #allowed status
    STATUS_FLOW = {
        'pending': ['confirmed', 'cancelled'],
        'confirmed': ['processing', 'cancelled'],
        'processing': ['shipped', 'cancelled'],
        'shipped': ['out_for_delivery', 'cancelled'],
        'out_for_delivery': ['delivered', 'cancelled'],
        'delivered': ['returned'],  # Can only be returned after delivery
        'cancelled': [],  # Cannot change from cancelled
        'returned': []  # Cannot change from returned    
    }

    if current_status == new_staus:
        return True, None
    
    #check if transaction is allowed 
    allowed_transitions = STATUS_FLOW.get(current_status, [])

    if new_staus not in allowed_transitions:
        return False, f"Cannot change status from '{current_status}' to '{new_staus}'. Please follow the proper order flow."
    return True, None


def update_order_status(order, new_status, changed_by=None, notes=None):
    """
    Update order status and create history
    Returns: (success, message)
    """
    old_status = order.status
    # status_changed = (old_status != new_status)
    is_valid, error_message = validate_status_transition(old_status, new_status)
    if not is_valid:
        return False, error_message
    
    # if old_status == 'cancelled' and new_status != 'cancelled':
    #     return False, "Cannot change status of cancelled order"
    
    # if old_status == 'delivered' and new_status not in ['returned', 'delivered']:
    #     return False, "Cannot change status of delivered oreder"

    # Update order status
    order.status = new_status    

    # Update payment status properly
    if new_status in ['confirmed', 'processing', 'shipped', 'out_for_delivery']:
        order.payment_status = 'pending'   # COD stays pending until delivered
    elif new_status == 'delivered':
        order.payment_status = 'completed'
        if not order.delivered_at:
            order.delivered_at = timezone.now()
            
    elif new_status == 'returned':
        order.payment_status = 'refunded'
    elif new_status == 'cancelled':
        order.payment_status = 'cancelled'

    order.save()
    
    # Update all order items to same status (except cancelled ones)
    order.items.exclude(status__in=['cancelled', 'returned', 'return_requested']).update(
        status=new_status,
        delivered_at=order.delivered_at if new_status == 'delivered' else None
    )

    # If you updated items via .update(),  Refresh items so templates show new status
    order.refresh_from_db()
    for item in order.items.all():
        item.refresh_from_db()

    OrderStatusHistory.objects.create(
        order=order,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        notes=notes or f"Status updated from {old_status} to {new_status}"
    )

    return True, f"Order status updated to {order.get_status_display()}"


def check_and_update_order_status_after_item_change(order):
    """
    Check if all items are cancelled/returned and update order status accordingly
    This is called after individual item cancellation or return
    """
    items = order.items.all()

    total_items = items.count()
    cancelled_items = items.filter(status='cancelled').count()
    returned_items = items.filter(status='returned').count()

    #if all items are cancelled
    if cancelled_items == total_items:
        old_status = order.status
        order.status = 'cancelled'
        order.payment_status = 'cancelled'
        order.cancelled_at = timezone.now()
        order.save()

        OrderStatusHistory.objects.create(
            order=order,
            old_status=old_status,
            new_status='cancelled',
            changed_by=None,
            notes="All items cancelled"
        )
    elif returned_items == total_items:
        old_status = order.status
        order.status = 'returned'
        order.payment_status = 'refunded'
        order.save()

        OrderStatusHistory.objects.create(
            order=order,
            old_status=old_status,
            new_status='returned',
            changed_by=None,
            notes="All items retunred"
        )


def search_orders(queryset, search_query):
    """
    Search orders by various fields
    """
    if not search_query:
        return queryset
    
    return queryset.filter(
        Q(order_id__icontains=search_query) |
        Q(user__email__icontains=search_query) |
        Q(user__first_name__icontains=search_query) |
        Q(user__last_name__icontains=search_query) |
        Q(full_name__icontains=search_query) |
        Q(mobile__icontains=search_query) 
    )


def filter_orders(queryset, filters):
    """
    Filter orders based on multiple criteria
    """
    if filters.get('status'):
        queryset = queryset.filter(status=filters['status'])

    if filters.get('payment_method'):
        queryset = queryset.filter(payment_method=filters['payment_method'])

    if filters.get('date_from'):
        queryset = queryset.filter(created_at__gte=filters['date_from'])

    if filters.get('date_to'):
        # Add one day to include the entire and date
        from datetime import timedelta
        date_to = filters['date_to'] + timedelta(days=1)
        queryset = queryset.filter(created_at__lt=date_to)

    return queryset


def get_order_statistics():
    """
    Get order statics for admin dashboard
    """
    from django.db.models import Count, Sum

    stats = Order.objects.aggregate(
        total_orders=Count('id'),
        pending_orders=Count('id', filter=Q(status='pending')),
        processing_orders=Count('id', filter=Q(status__in=['confirmed', 'processing'])),
        shipped_orders=Count('id', filter=Q(status__in=['shipped', 'out_for-delivery'])),
        delivered_orders=Count('id', filter=Q(status='delivered')),
        cancelled_orders=Count('id', filter=Q(status='cancelled')),
        total_revenue=Sum('total_amount', filter=Q(status='delivered'))
    )

    return stats


def get_low_stock_products(threshold=10):
    """Get products with stock below threshold"""
    from products.models import Product_varients

    return Product_varients.objects.filter(
        stock__lte=threshold,
        is__listed=True,
        product__is_listed=True
    ).select_related('product').order_by('stock')


def  get_out_of_stock_products():
    """Get products that are out of stock"""
    from products.models import Product_varients

    return Product_varients.objects.filter(
        stock=0,
        is_listed=True,
        product__is_listed=True
    ).select_related('product')


def get_order_total_discount(order):
    """returns total discount for an orer"""

    #product/offer discount
    item_discount = Decimal("0.00")
    for item in order.items.all():
        item_discount += item.discount_amount * item.quantity

    coupon_discount = Decimal("0.00")
    try:
        usage = CouponUsage.objects.filter(order=order).first()
        if usage:
            coupon_discount = usage.discount_amount
    except Exception:
        pass

    return item_discount + coupon_discount