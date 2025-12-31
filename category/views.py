from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from category.models import Category
from django.utils.text import slugify
# Create your views here.


#Category view---

@login_required(login_url='admin_login')
def category_list(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_login')

    search_query = request.GET.get('search','')
    parent_filter = request.GET.get('parent', '')

    categories = Category.objects.all().select_related('parent').order_by('-created_at') #get all categories inluding is_listed =False

    if search_query:
        categories = categories.filter(
            Q(category_name__icontains=search_query)|
            Q(description__icontains=search_query)|
            Q(slug__icontains=search_query)
        )

    if parent_filter:
        if parent_filter == 'main':
            categories = categories.filter(parent=None)
        else:
            categories = categories.filter(parent_id=parent_filter)


    paginator = Paginator(categories,3)
    page_number = request.GET.get('page')
    categories_page = paginator.get_page(page_number)

    #get main categories for filter
    main_categories = Category.objects.filter(parent=None, is_listed=True)

    context ={
        'categories' : categories_page,
        'search_query' : search_query,
        'parent_filter':parent_filter,
        'main_categories' : main_categories,
    }
    return render(request,'category_list.html',context)


@login_required(login_url='admin_login')
def add_category(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_login')
    
    #get main categories (Male/Female) for parent selection
    main_categories = Category.objects.filter(parent=None, is_listed=True).order_by('category_name')

    if request.method == 'POST':
        category_name = request.POST.get('category_name','').strip()
        description = request.POST.get('description','').strip()
        slug = request.POST.get('slug','').strip()
        parent_id = request.POST.get('parent', '')

        if not category_name:
            messages.error(request, 'Category name is required.')
            return render(request, 'add_category.html', {
                                'main_categories': main_categories,
                'category_name': category_name,
                'description': description,
                'slug': slug,
                'parent_id': parent_id,
            })
        # Allow only MEN and WOMEN as main categories
        # if parent_id == '' and category_name.lower() not in ['men', 'women']:
        #     messages.error(request, 'Only MEN and WOMEN can be added as main categories. All others must be subcategories.')

        if parent_id == '':
            if category_name.lower() not in ['men', 'women']:
                messages.error(request, 'You must select a parent category (Men or Women).')
                return render(request, 'add_category.html', {
                    'main_categories': main_categories,
                    'category_name': category_name,
                    'description': description,
                    'slug': slug,
                    'parent_id': parent_id,
                })

            parent_id = None

        # auto-generate slug if not provided
        if not slug:
            slug = slugify(category_name)
        else:
            slug = slugify(slug)

        #check if category already exists
        if Category.objects.filter(category_name__iexact=category_name).exists():
            messages.error(request, f'Category "{category_name}" already exists.')
            return render(request, 'add_category.html', {
                'category_name' : category_name,
                'description' : description,
                'slug' : slug,
                'main_categories' : main_categories,
                'parent_id': parent_id,
            })
        # Check if slug already exists
        if Category.objects.filter(slug=slug).exists():
            messages.error(request, f'Slug "{slug}" already exists. Please a different slug.')
            return render(request, 'add_category.html',{
                'category_name' : category_name,
                'description' : description,
                'slug' : slug,
                'main_categories' : main_categories,
                'parent_id': parent_id,                
            })

        #Create category
        Category.objects.create(
            category_name=category_name,
            description=description,
            slug=slug,
            parent_id=parent_id if parent_id else None,
            is_listed=True
        )

        messages.success(request, f'Category "{category_name}" added successfully.')
        return redirect('category_list')
    context = {
        'main_categories' : main_categories,
    }
    
    return render(request,'add_category.html', context)

#edit category
@login_required(login_url='admin_login')
def edit_category(request,category_id):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_login')
    
    category = get_object_or_404(Category, id=category_id)

     # Get main categories for parent selection (exclude current category and its children)
    main_categories =Category.objects.filter(parent=None, is_listed=True).exclude(id=category_id)


    if request.method == 'POST':
        category_name = request.POST.get('category_name','').strip()
        description = request.POST.get('description','').strip()
        slug = request.POST.get('slug','').strip()
        parent_id = request.POST.get('parent', '')

        #validation
        if not category_name:
            messages.error(request, 'Category name is required.')
            return render(request, 'edit_category.html',{
                'category':category,
                'main_categories': main_categories,
            })
        
        #auto generating slug if not provided
        if not slug:
            slug = slugify(category_name)
        else:
            slug=slugify(slug)

        #check if category name already exists (excluding current category)
        if Category.objects.filter(category_name__iexact=category_name).exclude(id=category_id).exists():
            messages.error(request, f'Category "{category_name}" already exists.')
            return render(request, 'edit_category.html', {
                'category' : category,
                'main_categories': main_categories,
            })
        
        # Check if slug already exists (excluding current category)  
        if Category.objects.filter(slug=slug).exclude(id=category_id).exists():
            messages.error(request, f'Slug "{slug}" already exists. Please use a different slug.')
            return render(request, 'edit_category.html', {
                'category': category,
                'main_categories': main_categories,
            })
        
        #update category
        category.category_name = category_name
        category.description = description
        category.slug = slug
        category.parent_id = parent_id if parent_id else None
        category.save()

        messages.success(request, f'Category "{category_name} " updated successfully. ')
        return redirect('category_list')
    context = {
        'category' : category,
        'main_categories': main_categories,
    }

    return render(request, 'edit_category.html', context)


#soft delete
@login_required(login_url='admin_login')
def toggle_category_status(request, category_id):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('admin_login')
    
    category = get_object_or_404(Category,id=category_id)

    if category.is_listed:
        category.is_listed = False
        messages.success(request, f'Category "{category.category_name}" has been unlisted(deleted)')
    else:
        category.is_listed = True
        messages.success(request, f'Category "{category.category_name}" has been listed(restored)')
    
    category.save()
    return redirect('category_list')
