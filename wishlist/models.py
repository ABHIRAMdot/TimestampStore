from django.db import models
from accounts.models import Account
from products.models import Product, Product_varients

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
        if not self.variant:
            return self.product.base_price
        
        base_price = self.variant.price
        
        # Check if product has an active offer
        if self.product.offer and self.product.offer.is_active:
            discount_percentage = self.product.offer.discount
            discount_amount = (base_price * discount_percentage) / 100
            return base_price - discount_amount
        
        return base_price
    
    def get_original_price(self):
        """Get original price without discount"""
        if self.variant:
            return self.variant.price
        return self.product.base_price
    
    def has_discount(self):
        """Check if product has active discount"""
        return self.product.offer and self.product.offer.is_active