from django.db import models
from django.urls import reverse
from django.utils import timezone

# Create your models here.

class Category(models.Model):
    category_name = models.CharField(max_length=50,unique=True)
    slug = models.SlugField(unique=True,blank=True,null=True)
    description = models.TextField(max_length=255,blank=True)
    
    # Parent = None → Male/Female | Parent = Category → Chain/Leather/Smartwatch
    parent = models.ForeignKey('self', on_delete=models.CASCADE,null=True, blank=True, )
    is_listed=models.BooleanField(default=True)   # soft delete (True=active, False=deleted)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'category'
        verbose_name_plural = 'categories'
        ordering = ['-created_at']

    def get_url(self):
        return reverse('products_by_category',args=[self.slug])

    def __str__(self):
        return self.category_name

class Offer(models.Model):
    name = models.CharField(max_length=200)
    category=models.ForeignKey(Category,on_delete=models.CASCADE,related_name='offers')
    
    discount = models.DecimalField(max_digits=5, decimal_places=2)
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

    def __str__(self):
        return f"{self.name} ({self.discount}%)"

    @property
    def is_active(self):
        """Returns True if the offer is currently active based on dates and status."""
        today = timezone.now().date()
        return self.status == 'active' and self.start_date <= today <= self.end_date
                              
    