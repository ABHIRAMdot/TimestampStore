from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .utils import has_purchased_product
from products.models import Product
from .models import Review
from .forms import ReviewForm


# Create your views here.


@login_required
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if not has_purchased_product(request.user, product):
        messages.error(request, "You can only review products you have purchsed.")
        return redirect('product_detail', slug=product.slug)
    
    #if review already exists - update it
    try:
        existing_review = Review.objects.get(user=request.user, product=product)
    except Review.DoesNotExist:
        existing_review = None
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=existing_review)

        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.product = product
            review.save()
            messages.success(request, "Your review has been submitted.")
            return redirect('product_detail', slug=product.slug)
    else:
        form = ReviewForm(instance=existing_review)
        
    return render(request, "reviews/add_reviews.html", {'form':form, 'product': product})