from django.db import models
from django.core.validators import MinValueValidator
from accounts.models import Account
from products.models import Product, Product_varients
from offers.utils import apply_offer_to_variant

# Create your models here.


class Cart(models.Model):
    """cart model"""
    user = models.OneToOneField(Account, on_delete=models.CASCADE, related_name='cart')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user.email}"
    
    def calculate_total(self):
        """calculate and update cart total"""
        total = sum(item.get_subtotal() for item in self.items.all())  # from the related foreignkey model(cartitem) 
        self.total = total
        self.save()
        return total
    
    def get_item_count(self):
        """Get total number of items in cart"""
        return sum(item.quantity for item in self.items.all())
    

class CartItem(models.Model):
    MAX_QUANTITY_PER_PRODUCT = 5   # Maximum quantity allowed per product

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(Product_varients, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=2)  #Price at the time of adding
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cart', 'product','variant')

    def __str__(self):
        return f"{self.quantity} × {self.product.product_name}"
    

    # def get_subtotal(self):
    #     """Calculate subtotal for this cart item"""
    #     return self.price * self.quantity

    def get_subtotal(self):
        """Always compute subtotal using the highest offer (product/category)."""
        offer_data = apply_offer_to_variant(self.variant)
        final_price = offer_data['final_price']
        return final_price * self.quantity

    def get_total_amount(self):
        """
        Always returns the latest payable cart total
        (used for payments, COD checks, wallet checks)
        """
        return sum(item.get_subtotal() for item in self.items.all())

    
    def get_available_stock(self):
        """Get available stock for the variant"""
        if self.variant:
            return int(self.variant.stock or 0)
        return 0
    
    def is_in_stock(self):
        """Check if the item is in stock"""
        return self.get_available_stock() > 0
    
    def can_increase_quantity(self):
        """Check if quantity can be increased"""
        if not self.variant:
            return False
        
        #check against stock
        if self.quantity >= self.variant.stock:
            return False
        
        #check against maximum allowed quantity
        if self.quantity >= self.MAX_QUANTITY_PER_PRODUCT:
            return False
        
        return True
    

    def is_product_available(self):
        """check  if product and variant are listed and available"""
        #check if product is listed
        if not self.product.is_listed:
            return False
        
        #check if category is listed
        if self.product.category and not self.product.category.is_listed:
            return False
        
        #check if variant is listed
        if self.variant and not self.variant.is_listed:
            return False
        
        return True