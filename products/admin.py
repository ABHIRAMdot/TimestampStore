from django.contrib import admin
from .models import Product, Product_varients, VariantImage

# Register your models here.


class ProductAdmin(admin.ModelAdmin):
    list_display = ("product_name", "slug")
    prepopulated_fields = {"slug": ("product_name",)}


admin.site.register(Product, ProductAdmin)


class VarientAdmin(admin.ModelAdmin):
    list_display = ("colour", "price", "stock", "product")


admin.site.register(Product_varients, VarientAdmin)
admin.site.register(VariantImage)
