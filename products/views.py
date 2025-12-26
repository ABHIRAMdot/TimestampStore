from django.shortcuts import render, redirect, get_object_or_404
from accounts.models import Account
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from django.contrib.auth.decorators import login_required
from category.models import Category
from products.models import Product, Product_varients,VariantImage
from django.utils.text import slugify

# Create your views here.


# Product view

@login_required(login_url='admin_login')
def product_list(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_login')

    search_query = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '')
    main_category_filter = request.GET.get('main_category', '')


    products = Product.objects.select_related('category').prefetch_related('varients__images').order_by('-created_at')
#search filter
    if search_query:
        products = products.filter(
            Q(product_name__icontains=search_query)|
            Q(description__icontains=search_query)|
            Q(category__category_name__icontains=search_query)
        )        

     # apply main category filter(male/female)
    if main_category_filter:
        products = products.filter(category__parent_id=main_category_filter)

    # apply category filter
    if category_filter:
        products = products.filter(category_id=category_filter)

    sort = request.GET.get('sort', '')

    if sort == 'newest':
        products = products.order_by('-created_at')
    elif sort == 'oldest':
        products = products.order_by('created_at')
    elif sort == 'price_low':
        products = products.order_by('base_price')
    elif sort == 'price_high':
        products = products.order_by('-base_price')
    


    paginator = Paginator(products,3)
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)



    #get all main categories(parent=None) for filter
    main_categories = Category.objects.filter(is_listed =True, parent=None).order_by('category_name')

    #get all sub categories for filter dropdown
    subcategories = Category.objects.filter(is_listed=True, parent__isnull=False).order_by('category_name')

    context = {
        'products' :products_page,
        'search_query' : search_query,
        'category_filter' : category_filter,
        'main_category_filter': main_category_filter,
        'subcategories' : subcategories,
        'main_categories': main_categories,
        'sort':sort,

    }

    return render(request, 'product_list.html', context)


#add product 
@login_required(login_url='admin_login')
def add_product(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_login')
    
    #Get only subcategories(with parent)
    categories = Category.objects.filter(is_listed=True, parent__isnull=False).select_related('parent').order_by('parent__category_name', 'category_name')

    if request.method == 'POST':
        product_name = request.POST.get('product_name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        slug = request.POST.get('slug', '').strip()
        base_price = request.POST.get('base_price', '').strip()

        #Get varient data
        colours = request.POST.getlist('colour[]')
        prices = request.POST.getlist('price[]')
        stocks = request.POST.getlist('stock[]')

        # validation

        if not product_name:
            messages.error(request, 'Product name is required.')
            return render(request, 'add_prouct.html', {
                'categories' : categories,
            })
        
        if not category_id:
            messages.error(request, 'Please select a category.')
            return render(request, 'add_product.html', {
                'categories': categories,
            })
        
        if not description:
            messages.error(request, 'Description is required.')
            return render(request, 'add_product.html', {
                'categories': categories,
            })
        if not base_price:
            messages.error(request,"Base price is required")
            return render(request, 'add_product.html', {
                'categories': categories,
            })
        try:
            base_price = float(base_price)
            if base_price <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Please enter a valid base price')   
            return render(request, 'add_product.html', {
                'categories': categories,
            })        

        # auto-generate slug if not provided
        if not slug:
            slug = slugify(product_name)
        else:
            slug = slugify(slug)    



        #  Collect all variant images ---
        variant_images = {}
        for key in request.FILES.keys():
            if key.startswith('variant_images_'):
                variant_images[key] = request.FILES.getlist(key)

        if not variant_images:
            messages.error(request, 'Please upload at least one variant with images.')
            return render(request, 'add_product.html', {
                'categories': categories,
                })

        if not colours or len(colours) == 0:
            messages.error(request, 'Please add at least one product variant.')
            return render(request, 'add_product.html', {
                'categories': categories,
            })
        
        # validate that all varients have required filed
        for i in range(len(colours)):
            if not colours[i] or not prices[i]:
                messages.error(request, f' Varient {i+1}: colour and price are required.')
                return render(request, 'add_product.html', {
                'categories': categories,
                })
            try:
                float(prices[i])
            except ValueError:
                messages.error(request, f'Variant {i+1}: Invalid price format.')
                return render(request, 'add_product.html', {
                    'categories': categories,
                })                
        

        
        #check if product name already exists
        if Product.objects.filter(product_name__iexact=product_name).exists():
            messages.error(request, f'Product "{product_name}" already exists.')
            return render(request, 'add_product.html', {
                'categories': categories,
            })

        # check if slug already exists
        if Product.objects.filter(slug=slug).exists():
            messages.error(request, f'Slug "{slug}" already exists. Please use a different slug.')
            return render(request, 'add_product.html', {
                'categories': categories,
            })
        
        try:
            with transaction.atomic():
                #now create product
                product = Product.objects.create(
                    product_name=product_name,
                    slug=slug,
                    description=description,
                    base_price=base_price,
                    category_id=category_id,
                    is_listed=True
                )

                # Loop over all variants (colour, price, stock)
                for i in range(len(colours)):
                    if colours[i] and prices[i]:
                        variant_obj = Product_varients.objects.create(
                            product=product,
                            colour=colours[i],
                            price=prices[i],
                            stock=stocks[i] if stocks[i] else 0,
                            is_listed=True,

                        )
                    # Save images for this variant
                    images = request.FILES.getlist(f'variant_images_{i}[]') or []

                    if not images or len(images) < 3:
                        raise ValueError(f'Variant {i+1} must have at least 3 images.')
                    #save imge
                    for index, img in enumerate(images):
                        VariantImage.objects.create(
                            variant=variant_obj,
                            image=img,
                            is_listed=True,
                            is_primary=(index == 0)  # first image is primary
                        )

                messages.success(request, f'Product "{product_name}" added successfully.')
                return redirect('product_list')
        except Exception as e:
            messages.error(request, f'Error adding product: {str(e)}')
            return render(request, 'add_product.html', {'categories':categories})
    context = {
        'categories':categories,
    }
    return render(request, 'add_product.html', context)


# edit product
@login_required(login_url='admin_login')
def edit_product(request, product_id):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_login')
    
    product = get_object_or_404(Product, id=product_id)
    categories = Category.objects.filter(is_listed=True,parent__isnull=False).select_related('parent').order_by('parent__category_name','category_name')
    main_categories = Category.objects.filter(is_listed =True, parent=None).order_by('category_name')


    if request.method == 'POST':
        product_name = request.POST.get('product_name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category', '')
        slug = request.POST.get('slug', '').strip()
        base_price = request.POST.get('base_price', '').strip()

        # Get variant data
        colours = request.POST.getlist('colour[]')
        prices = request.POST.getlist('price[]')
        stocks = request.POST.getlist('stock[]')
        variant_ids = request.POST.getlist('variant_id[]') #existing variants
        delete_variants = request.POST.getlist('delete_variants') #variants to delete

        # Get images to delete
        delete_image_ids = request.POST.getlist('delete_images')

        if not product_name:
            messages.error(request, 'Product name is required.')
            return render(request, 'edit_product.html', {
                'product' : product,
                'categories' : categories,
            })
        if not description:
            messages.error(request, 'description is required.')
            return render(request, 'edit_product.html', {
                'product' : product,
                'categories' : categories,
            })
        # auto generate slug
        if not slug:
            slug = slugify(product_name)
        else:
            slug =  slugify(slug)

        if not base_price:
            messages.error(request, 'Base price is required.')
            return render(request, 'edit_product.html', {
                'product': product,
                'categories': categories,
            })

        try:
            base_price = float(base_price)
            if base_price <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Please enter a valid base price.')
            return render(request, 'edit_product.html', {
                'product': product,
                'categories': categories,
            })
        
        if Product.objects.filter(product_name__iexact=product_name).exclude(id=product_id).exists():
            messages.error(request, f'Product "{product_name}" already exists')
            return render(request, 'edit_product.html', {
                'product' : product,
                'categories' : categories,
            })

 
        if Product.objects.filter(slug=slug).exclude(id=product_id).exists():
            messages.error(request, f'Slug "{slug}" already exists. Please use a different slug.')
            return render(request, 'edit_product.html', {
                'product' :product,
                'categories' : categories,
            })

        try:
            with transaction.atomic():
                #update product
                product.product_name = product_name
                product.description = description
                product.base_price = base_price
                product.category_id = category_id
                product.slug = slug
                product.save()

                # Delete selected images
                if delete_image_ids:
                    VariantImage.objects.filter(id__in=delete_image_ids).delete()

                #Handling deleting selected variants(and their images cascade automatically)
                if delete_variants:
                    Product_varients.objects.filter(id__in=delete_variants, product=product).delete()

                #update existing variants
                for i in range(len(variant_ids)):
                    if variant_ids[i] and str(variant_ids[i]) not in delete_variants:
                        variant_obj = Product_varients.objects.get(id=variant_ids[i], product=product)
                        variant_obj.colour = colours[i]
                        variant_obj.price = prices[i]
                        variant_obj.stock = stocks[i] if stocks[i] else 0
                        variant_obj.save()

                        #Update or add new images for existing variant
                        new_imgs = request.FILES.getlist(f'variant_images_{i}[]') or []
                        for img in new_imgs:
                            VariantImage.objects.create(
                                variant=variant_obj,
                                image=img,
                                is_listed=True,
                                is_primary=False
                            )
                        
                        #handle primary image changes
                        primary_image_key = f'set_primary_{variant_ids[i]}'
                        if primary_image_key in request.POST:
                            new_primary_id = request.POST.get(primary_image_key)
                            if new_primary_id:
                                #remove primary from all images in this vaiant
                                VariantImage.objects.filter(variant=variant_obj).update(is_primary=False)
                                #set new primary
                                VariantImage.objects.filter(id=new_primary_id, variant=variant_obj).update(is_primary=True)

                # Add new variants (those without variant_id)
                new_variant_start = len(variant_ids)
                if len(colours) > new_variant_start:
                    for i in range(new_variant_start, len(colours)):
                        if colours[i] and prices[i]:
                            new_variant = Product_varients.objects.create(
                                product=product,
                                colour=colours[i],
                                price=prices[i],
                                stock=stocks[i] if stocks[i] else 0,
                                is_listed=True
                            )
                            # add images for this new variant
                            images = request.FILES.getlist(f'variant_images_{i}[]') or []
                            if len(images) >= 3:
                                for index, img in enumerate(images):
                                    VariantImage.objects.create(
                                        variant=new_variant,
                                        image=img,
                                        is_listed=True,
                                        is_primary=(index ==0 )
                                    )
                            else:
                                raise ValueError(f'Variant {i+1} must have at least 3 images')
                            
                all_variants = product.varients.all()
                for idx, variant in enumerate(all_variants, 1):
                    image_count = variant.images.count()
                    if image_count < 3:
                        raise ValueError(f'Variant {idx} ({variant.colour}) must have at least 3 images (currently has {image_count})')

                messages.success(request, f'Product "{product_name}" updated successfully.')
                return redirect('product_list')
        except Exception as e:
            messages.error(request, f'Error upting product: {str(e)}')
    context = {
        'product' : product,
        'categories' : categories,
        'main_category' : main_categories,
    }
    return render(request, 'edit_product.html', context)

#Toggle Product status (soft Delte) 
@login_required(login_url='admin_login')
def toggle_product_status(request, product_id):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('admin_login')
    
    product = get_object_or_404(Product, id=product_id)

    if product.is_listed:
        product.is_listed = False
        messages.success(request, f'Product "{product.product_name}"has been unlisted.')
    else:
        product.is_listed =True
        messages.success(request, f'Product "{product.product_name}" has been listed.')
    product.save()
    return redirect('product_list')

@login_required(login_url='admin_login')
def view_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'view_product.html', {'product': product})



@login_required(login_url='admin_login')
def manage_variants(request, product_id):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_login')

    product = get_object_or_404(Product, id=product_id)
    variants = product.varients.all().order_by('colour')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add':
            colour = request.POST.get('colour')
            price = request.POST.get('price')
            stock = request.POST.get('stock', 0)

            if not colour or not price:
                messages.error(request, 'Colour and price are required.')
            else:
                try:
                    Product_varients.objects.create(
                        product=product,
                        colour=colour,
                        price=price,
                        stock=stock,
                        is_listed=True
                    )
                    messages.success(request, f'Variant "{colour}" added successfully ')
                    return redirect('mange_variants', product_id=product_id)
                except Exception as e:
                    messages.error(request, f'Error adding variant: {(e)}')
        elif action == 'update':
            variant_id = request.POST.get('variant_id')
            variant = get_object_or_404(Product_varients, id=variant_id, product=product)

            price = request.POST.get('price')
            stock = request.POST.get('stock', 0)

            if price:
                variant.price = price
                variant.stock = stock
                variant.save()
                messages.success(request, f'variant updated successfully')
                return redirect('manage_variants', product_id=product_id)
    context = {
        'product' : product,
        'variants' : variants,
    }
    return render(request, 'manage_variants.html', context)

#Toggle varient status
@login_required(login_url='admin_login')
def toggle_variant_status(request, variant_id):
     if not request.user.is_superuser:
         messages.error(request, 'You do not hvae permission to perform this action.')
         return redirect('admin_login')
     
     variant = get_object_or_404(Product_varients, id=variant_id)

     variant.is_listed =  not variant.is_listed
     variant.save()

     status = "listed" if variant.is_listed else "unlisted"
     messages.success(request, f'Variant has been {status}.')

     return redirect('view_product', product_id=variant.product.id)



        