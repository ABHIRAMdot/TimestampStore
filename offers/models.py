from django.db import models
from django.utils import timezone
from category.models import Category
from products.models import Product


import logging

logger = logging.getLogger('project_logger')


#base offer model (Abstract)
class BaseOffer(models.Model):
    """Abstract base model contains common fields"""

    name =  models.CharField(max_length=200)
    discount = models.DecimalField(max_digits=5, decimal_places=2, help_text="Discount percentage (0-100)" )
    
    start_date = models.DateField()
    end_date = models.DateField()

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('expired', 'Expired'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        abstract = True
        ordering = ['-created_at']
    
    @property
    def is_active(self):
        """checks the order is currenly valid
        - Allows us to call: offer.is_active (like an attribute)        
        """

        today = timezone.now().date()

        return (
            self.status == 'active' and self.start_date <= today <= self.end_date       # return ture if today's date is between start_date and end_date else False
    
        )  
    
    def __str__(self):
        """
        String representation shown in Django admin.
        Example: "Summer Sale (30%) 
        """
        return f"{self.name} ({self.discount}%)"
    
    
class CategoryOffer(BaseOffer):
    """Offer applied to entire category"""

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='category_offers')

    class Meta:
        ordering = ['created_at']


class ProductOffer(BaseOffer):
    """Order appied to specific priduct """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_offers')

    class Meta:
        ordering = ['created_at']



