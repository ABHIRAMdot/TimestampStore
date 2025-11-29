from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Min, Max, Q
from django.http import JsonResponse
from products.models import Product, VariantImage
from django.core.paginator import Paginator
from category.models import Category
import math
from django.urls import reverse




# Create your views here.

def home_page(request):
    products = (
        Product.objects.filter(is_listed=True, varients__is_listed=True, varients__stock__gt=0)
        .annotate(min_price=Min('varients__price')).prefetch_related('varients__images','varients', 'category').distinct()  #to prevent duplicte products
        .order_by('-created_at')[:4]
    )

    # attach min price variant to each product for template access
    for product in products:
        product.min_variant = product.varients.filter(is_listed=True, price=product.min_price).first()


    #get main categories for navbar dropdown(parent categories only)
    main_categories = Category.objects.filter(parent__isnull=True, is_listed=True).order_by('category_name')

    return render(request, 'home/home.html', {'products': products, 'main_categories' : main_categories })


def user_product_list(request):
    """ product listing wiith filter adnsearch """
    products = Product.objects.filter(is_listed=True, varients__is_listed=True, varients__stock__gt=0).annotate(min_price=Min('varients__price')).prefetch_related('varients__images','varients', 'category')

    main=request.GET.get('main')
    if main:
        # filter by parent slug
        products = products.filter(category__parent__slug=main)

    # filter- sub category
    category = request.GET.get('category')
    if category:
        products = products.filter(category__slug=category)


    search = request.GET.get('search')
    if search:
        products = products.filter(product_name__icontains=search)
    
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    if min_price:
        products = products.filter(varients__price__gte=min_price)
    if max_price:
        products = products.filter(varients__price__lte=max_price)
    
    #remove duplicate product from price filtering
    products = products.distinct()

    # sorting
    sort = request.GET.get('sort')
    if sort == 'price_low':
        products = products.order_by('min_price')
    elif sort == 'price_high':
        products = products.order_by('-min_price')
    elif sort == 'name_asc':
        products = products.order_by('product_name')
    elif sort == 'name_desc':
        products = products.order_by('-product_name')
    elif sort == 'new':
        products = products.order_by('-created_at')


    highest_variant_price = products.aggregate(
        Max('varients__price')
    )['varients__price__max'] or 10000

    #  Round up to nearest 5000 
    rounded_max_price = math.ceil(int(highest_variant_price) / 5000) * 5000

    paginator = Paginator(products, 4)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)


    #attach min price variant to each product for consistent display
    for product in products_page:
        product.min_variant = product.varients.filter(is_listed=True, price=product.min_price).first()

    categories = Category.objects.filter(parent__isnull=False, is_listed=True)

    breadcrumbs = [
        {"label": "Home", "url": reverse("home")},
    ]

    return render(request, 'home/user_product_list.html', {
        'products': products_page,
        'categories': categories,
        'request': request,    #Important for retaining filter values
        'max_price': rounded_max_price,
        'breadcrumbs': breadcrumbs,
    })


def user_product_detail(request, slug):
    """ display product detail page with variants """
    try:
        product = Product.objects.get(slug=slug)
    except Product.DoesNotExist:
        # Product completely missing
        return render(request, "errors/product_unavailable.html", status=404)
    
    #Block unlisted product even user came erlier
    if not product.is_listed:
        return render(request, "errors/product_unavailable.html", status=404)
    

    # get only listed varients ordered by price(lowest first)
    #order variants by price to show cheapest first
    variants = product.varients.filter(is_listed=True).order_by('price', 'colour')
    if not variants.exists():
        messages.error(request, '"This product has no availble varients.')
        return redirect('user_product_list')
    
    selected_variant_id = request.GET.get("variant")
    if selected_variant_id:
        selected_variant = variants.filter(id=selected_variant_id).first()
        if not selected_variant:
            # invalid variant id, use cheapest varient
            selected_variant = variants.first()
    else:
        # Default to ceapest variant
        selected_variant = variants.first()

    #checking this is an AJAX request, return JASON response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if not product.is_listed or not variants.exists():
            return JsonResponse({
                'available': False,
                'redirect_url': '/product-unavailable/'
            })
        return JsonResponse({
            'available': True,
            'stock': selected_variant.stock,
            'price': float(selected_variant.price)
        })
    
    #get images for the selected variant
    variant_images = VariantImage.objects.filter(variant=selected_variant, is_listed=True).order_by('-is_primary', 'id')

    if not variant_images:
        messages.error(request, "This product variant currently has no images available.")

    #related products (same category, exclude current)
    related = (
        Product.objects.filter(is_listed=True, category=product.category, varients__is_listed=True, varients__stock__gt=0)
        .exclude(id=product.id).annotate(min_price=Min('varients__price'))
        .prefetch_related('varients__images', 'varients').distinct()[:8]
        )
    #attach min price variant to realated products
    for related_product in related:
        related_product.min_variant = related_product.varients.filter(is_listed=True, price=related_product.min_price).first()

    #get main categories for navbar
    main_categories = Category.objects.filter(parent__isnull=True, is_listed=True).order_by('category_name')

    breadcrumbs = [
        {"label": "Home", "url": reverse("home")},
        {"label": "All Products", "url": reverse("user_product_list")},
        
    ]

    return render(request, 'home/user_product_detail.html', {
        'product': product,
        'variants': variants,
        'selected_variant': selected_variant,
        'variant_images': variant_images,
        'related': related,
        'main_categories' : main_categories,
        'breadcrumbs': breadcrumbs,
        
    }) 

def product_unavailable(request):
    return render(request, "errors/product_unavailable.html", status=410)

def custom_404(request, exception):     # only works in DEBUG = False
    return render(request, '404.html', status=404)