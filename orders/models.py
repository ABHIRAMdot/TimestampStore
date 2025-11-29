from django.db import models
from django.core.validators import MinValueValidator
from accounts.models import Account, Address
from products.models import Product, Product_varients
from django.utils import timezone
import uuid
from decimal import Decimal



class Order(models.Model):
    """Main order model"""

    #order identification
    order_id = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="orders")
    # shipping info
    shipping_address = models.ForeignKey(Address, on_delete=models.CASCADE,null=True, related_name="orders")
    full_name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15)
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)

    # order status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]

    status = models.CharField(max_length=200, choices=STATUS_CHOICES, default='pending')

    # payment info
    PAYMENT_METHOD_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('online', 'Online Payment'),
        ('wallet', 'Wallet'),
    ]

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, choices=[
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('refunded', 'Refunded'),
        ], default='pending')

    #pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    #tracking
    tracking_number = models.CharField(max_length=100, blank=True, null=True)

    # Notes and cancellation
    order_notes = models.TextField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    cancelled_by = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name="cancelled_orders")
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['order_id']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]

    #order ID generator 
    def save(self, *args, **kwargs):
        if not  self.order_id:
            # Generate unique order ID: TS + timestamp + random
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            random_part = str(uuid.uuid4().int)[:4]
            self.order_id = f"TS{timestamp}{random_part}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_id} - {self.user.email}"
    
    @property
    def can_be_cancelled(self):
        """Check if order can be cancelled"""
        return self.status in ['pending', 'confirmed', 'processing']
    
    #Returns allowed only within 7 days of delivery.
    @property
    def can_be_returned(self):
        """Check if order can be returned"""
        if self.status != 'delivered' or not self.delivered_at:
            return False

        # Allow returns within 7 days of delivery
        days_since_delivery = (timezone.now() - self.delivered_at).days
        return days_since_delivery <= 7 
    
    @property
    def total_refund_amount(self):
        """Total refunded amount for this order (cancelled + returned items)."""
        refunded_items = self.items.filter(status__in=['cancelled', 'returned'])
        total = Decimal('0.00')
        for item in refunded_items:
            total += item.refund_amount
        return total
    

    def get_cancellable_items(self):
        """Get items that can be cancelled"""
        return self.items.filter(
            status__in=['pending', 'confirmed', 'processing']
        )

    def get_returnable_items(self):
        """Get items that can be returned"""
        return self.items.filter(status='delivered')
    
    def calculate_totals(self):
        """Calculate order totals from items after cancel/ return"""
        active_items = self.items.exclude(status__in=['cancelled', 'returned'])
        self.subtotal = sum(item.get_total() for item in active_items)
        
        # Calculate discount
        self.discount_amount = sum(
            item.discount_amount * item.quantity 
            for item in active_items 
        )
        
        # Shipping charge (free for orders above 1000)
        if self.subtotal >= 2000:
            self.shipping_charge = Decimal('0.00')
        else:
            self.shipping_charge = Decimal('50.00')
        
        self.total_amount = self.subtotal + self.shipping_charge
        self.save()
    
    def update_status_based_on_items(self):
        """Update order status based on item statuses"""
        items = list(self.items.all())
        for item in items:
            item.refresh_from_db()
        
        if not items.exists():
            return
        
        item_statuses = set(items.values_list('status', flat=True))
        
        # If all items cancelled
        if item_statuses == {'cancelled'}:
            self.status = 'cancelled'
            self.save()
        # If all items delivered
        elif item_statuses == {'delivered'}:
            self.status = 'delivered'
            if not self.delivered_at:
                self.delivered_at = timezone.now()
            self.save()
        # If mix of delivered and cancelled
        elif item_statuses.issubset({'delivered', 'cancelled'}):
            self.status = 'delivered'
            if not self.delivered_at:
                self.delivered_at = timezone.now()
            self.save()              


class OrderItem(models.Model):
    """Individual items in an order"""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(Product_varients, on_delete=models.CASCADE)

    #product details at the time of order
    product_name = models.CharField(max_length=200)
    variant_colour = models.CharField(max_length=20)

    #pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    #Item Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('return_requested', 'Return Requested'),
        ('returned', 'Returned'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    #cancellation and return
    cancellation_reason = models.TextField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    return_reason = models.TextField(blank=True, null=True)
    return_request_at = models.DateTimeField(blank=True, null=True)
    returned_at = models.DateTimeField(null=True, blank=True)

    #Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at =models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.product_name} - {self.variant_colour} (x{self.quantity})"
    
    def get_total(self):
        """Calculate total for this item"""
        return self.price * self.quantity
    @property
    def can_be_cancelled(self):
        return self.status in ['pending', 'confirmed', 'processing']
    @property
    def can_be_returned(self):
        if self.status != 'delivered' or not self.delivered_at:
            return False
        
        days_since_delivery = (timezone.now() - self.delivered_at).days
        return days_since_delivery <= 7
    
    def cancel_item(self, reason=None, cancelled_by=None):
        """Cancel this item and restore stock"""
        if not self.can_be_cancelled:
            return False, "This item cannot be cancelled"
        
        #Restore stock
        self.variant.stock += self.quantity
        self.variant.save()

        #Update item status
        self.status = 'cancelled'
        self.cancellation_reason = reason
        self.cancelled_at = timezone.now()
        self.save()

        #Update order totals
        self.order.calculate_totals()
        self.order.update_status_based_on_items()

        return True, "Item cancelled successfully"
    
    def request_return(self, reason):
        """Request return for this item"""
        if not self.can_be_returned:
            return False, "This item cannot be returned"
        
        if not reason or not reason.strip():
            return False, "Return reason is required"
        
        self.status = 'return_requested'
        self.return_reason = reason
        self.return_request_at = timezone.now()
        self.save()

        return True, "Return request submitted successfully"
    
    def approve_return(self):
        """Approve return and restore stoock(admin action)"""
        if self.status != 'return_requested':
            return False, "No return request found"
        
        #Restore stock
        self.variant.stock += self.quantity
        self.variant.save()

        self.status = 'returned'
        self.returned_at = timezone.now()
        self.save()

        #Update order totals
        self.order.calculate_totals()
        self.order.update_status_based_on_items()

        return True, "Return approved and stock restored"

    @property
    def refund_amount(self):
        """Amount refunded for this cancelled/returned item."""
        if self.status in ['cancelled', 'returned']:
            return self.price * self.quantity
        return Decimal('0.00')


    
class OrderStatusHistory(models.Model):
    """Track status changes for orders"""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name='status_changes')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Order Status Histories'

    def __str__(self):
        return f"{self.order.order_id}: {self.old_status} -> {self.new_status}"

