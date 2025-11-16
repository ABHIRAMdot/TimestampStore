from category.models import Category

def navbar_context(request):
    """Make main categories available in all templates"""
    main_categories = Category.objects.filter(
        parent__isnull=True, 
        is_listed=True
    ).order_by('category_name')
    
    return {
        'main_categories': main_categories,
    }