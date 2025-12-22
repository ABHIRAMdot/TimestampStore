from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from accounts.models import Account

# Create your models here.

class Coupon(models.Model):
    
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)

    discount_type = models.CharField(
        max_length=20,
        choices=[('fixed', 'Fixed Amount'), ('percentage', 'Percentage')],
        default='fixed'
    )

    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Applicable only when discount_type = percentage"
    )

    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])


    min_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2,default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])

    start_date = models.DateField()
    end_date = models.DateField()

    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Total times this coupon can be used (leave empty for unlimited)")
    times_used = models.PositiveIntegerField(default=0, help_text="How many time this coupon has been used")

    one_time_use = models.BooleanField(default=True, help_text="Each user can use this coupon only once")

    is_active = models.BooleanField(default=True, help_text="currently active")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.discount_type == 'percentage':
            return f"{self.code} {self.discount_percentage}% off"
        return f"{self.code} ₹{self.discount_amount} off"

    
    def is_valid(self):
        """check validity (date + active status)"""

        today = timezone.now().date()

        if not self.is_active:
            return False, "This coupon is currently inactive"
        
        if today < self.start_date:
            return False, f"This coupon is valid from {self.start_date}"
        
        if today > self.end_date:
            return False, "This coupon has expired."
        
        if self.usage_limit and self.times_used >= self.usage_limit:
            return False, "This coupon has reached its usage limits."
        
        return True, "Valid"   #else valid
    
    def can_user_use(self, user):
        """check a specific user can use this"""

        is_valid, message = self.is_valid()
        if not is_valid:
            return False, message

        if self.one_time_use:
            already_used = CouponUsage.objects.filter(coupon=self, user=user).exists()

            if already_used:
                return False, "You have already used this coupon."
            
        return True, "You can use this coupon"
    
    def calculate_discount(self, cart_total):
        """
        Calculate discount based on type (fixed / percentage) for given cart total
        Returns: (discount_amount, final_total)
        """

        cart_total = Decimal(str(cart_total))

        #fixed discount amount
        if self.discount_type == 'fixed':
            discount = self.discount_amount
            #don't discount more than cart total
            discount = min(discount, cart_total)

        elif self.discount_type == 'percentage':
            if not self.discount_percentage:
                return Decimal('0.00'), cart_total
            
            discount = (cart_total * (self.discount_percentage/ Decimal('100'))).quantize(Decimal("0.01"))

        else:
            discount = Decimal('0.00')            

        final_total = cart_total - discount

        return discount, final_total
    

class CouponUsage(models.Model):
    """Track which user used which coupon"""

    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="usages")
    user = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="coupon_usages")

    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name="coupon_usage", help_text="Which order used this coupon")

    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Actual discount applied")
    cart_total_before_discount = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ['-used_at']
        unique_together = ['coupon', 'order']

    def __str__(self):
        return f"{self.user.email} used {self.coupon.code} - ₹{self.discount_amount} off."