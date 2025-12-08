# from django.db import models
# from category.models import Category# Create your models here.


# class Offer(models.Model):
#     name = models.CharField(max_length=200)
#     category=models.ForeignKey(Category,on_delete=models.CASCADE,related_name='offers')
    
#     discount = models.DecimalField(max_digits=5, decimal_places=2)
#     start_date = models.DateField()
#     end_date = models.DateField()
    
#     STATUS_CHOICES = [
#         ('active', 'Active'),
#         ('inactive', 'Inactive'),
#         ('expired', 'Expired'),
#     ]
#     status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    
#     description = models.TextField(blank=True, null=True)
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return f"{self.name} ({self.discount}%)"

#     @property
#     def is_active(self):
#         """Returns True if the offer is currently active based on dates and status."""
#         today = timezone.now().date()
#         return self.status == 'active' and self.start_date <= today <= self.end_date
                              
    
