from django.db import models
from decimal import Decimal
from accounts.models import Account
from products.models import Product, Product_varients
from offers.utils import get_best_offer_for_product, calculate_discounted_price

# Create your models here.

class Wishlist(models.Model):
    user = models.OneToOneField(Account, on_delete=models.CASCADE, related_name='wishlist')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wishlist for {self.user.email}"
    
    def get_item_count(self):
        """Get total number of items in wishlist"""
        return self.items.count()
    
    def has_item(self, product, variant=None):
        """Check if product/variant is in wishlist"""
        if variant:
            return self.items.filter(product=product, variant=variant).exists()
        return self.items.filter(product=product).exists()


class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(Product_varients, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wishlist', 'product', 'variant')
        ordering = ['-created_at']

    def __str__(self):
        variant_info = f" - {self.variant.colour}" if self.variant else ""
        return f"{self.product.product_name}{variant_info}"
    
    def is_product_available(self):
        """Check if product and variant are listed and available"""
        # Check if product is listed
        if not self.product.is_listed:
            return False
        
        # Check if category is listed
        if self.product.category and not self.product.category.is_listed:
            return False
        
        # Check if variant is listed
        if self.variant and not self.variant.is_listed:
            return False
        
        return True
    
    def is_in_stock(self):
        """Check if the item is in stock"""
        if self.variant:
            return self.variant.stock > 0
        return False
    
    def get_price(self):
        """Get current price (with discount if applicable)"""
        base_price = self.variant.price if self.variant else self.product.base_price

        offer_info = get_best_offer_for_product(self.product)

        if not offer_info:
            return Decimal(str(base_price)).quantize(Decimal('0.01'))
        

        discount_percentage = offer_info.get('discount_percentage') or Decimal('0')
        # use existing calculate_discounted_price to compute final price (keeps rounding consistent)
        final_price = calculate_discounted_price(base_price, discount_percentage)
        
        return final_price
    
    def get_original_price(self):
        """Get original price without discount"""
        if self.variant:
            return self.variant.price
        return self.product.base_price
    
