from django.db import models
from category.models import Category
from django.db.models import Avg, Count

# Create your models here.

class Product(models.Model):
    product_name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    is_listed =models.BooleanField(default=True)
    
    category = models.ForeignKey(Category,on_delete=models.SET_NULL,null=True,blank=True)

    # offer = models.ForeignKey(Offer,on_delete=models.SET_NULL, null=True, blank=True,related_name='products')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  

    def __str__(self):
        return self.product_name
    class Meta:
        ordering = ['-created_at']

    @property
    def avg_rating(self):
        return self.reviews.aggregate(avg=models.Avg('rating'))['avg'] or 0
    

    @property
    def review_count(self):
        return self.reviews.count()

    @property
    def rating_distribution(self):
        """Returns dict like {5:10, 4:3, 3:1, 2:0, 1:0}"""
        dist = self.reviews.values('rating').annotate(count=Count('rating'))
        data = {i: 0 for i in range(1, 6)}
        for d in dist:
            data[d['rating']] = d['count']
        return data


class Product_varients(models.Model):
    product = models.ForeignKey(Product ,on_delete=models.CASCADE,related_name='varients')

    COLOUR_CHOICES = [
        ('Black', 'Black'),
        ('Blue', 'Blue'),
        ('Brown', 'Brown'),
        ('White', 'White'),
        ('Red', 'Red'),
        ('Green', 'Green'),
        ('Yellow', 'Yellow'),
        ('Gray', 'Gray'),
        ('Silver', 'Silver'),
        ('Gold', 'Gold'),
    ]

    colour = models.CharField(max_length=20, choices=COLOUR_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    is_listed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['colour']
        unique_together = ['product', 'colour']

    def __str__(self):
        return f"{self.product.product_name} - {self.colour}"


# CHANGED: Renamed from Product_images to VariantImage and linked to variant
class VariantImage(models.Model):
    variant = models.ForeignKey(Product_varients, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='photos/variants/%Y/%m/%d/')
    is_primary = models.BooleanField(default=False)
    is_listed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ['-is_primary', 'created_at']


    def __str__(self):
        return f"{self.variant.product.product_name} - {self.variant.colour} Image"

