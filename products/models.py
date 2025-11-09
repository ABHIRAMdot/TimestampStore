from django.db import models
from category.models import Category,Offer

# Create your models here.

class Product(models.Model):
    product_name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    is_listed =models.BooleanField(default=True)
    
    category = models.ForeignKey(Category,on_delete=models.SET_NULL,null=True,blank=True)

    offer = models.ForeignKey(Offer,on_delete=models.SET_NULL, null=True, blank=True,related_name='products')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  

    def __str__(self):
        return self.product_name
    class Meta:
        ordering = ['-created_at']

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

class Product_images(models.Model):
    product = models.ForeignKey(Product ,on_delete=models.CASCADE,related_name='images')
    image_url = models.ImageField(upload_to='photos/products/%Y/%m/%d/')
    is_listed = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_primary','created_at']

    def __str__(self):
        return f"Image for {self.product.product_name}"