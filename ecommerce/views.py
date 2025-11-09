from django.shortcuts import render
from products.models import Product,Product_varients,Product_images

def home (request):
    products = Product.objects.filter(is_listed = True).prefetch_related('varients','images')
    

    context = {
        'products' : products,
    }
    return render(request,'home.html',context)