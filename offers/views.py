from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import date
from django.urls import reverse
from .models import CategoryOffer, ProductOffer
from category.models import Category
from products.models import Product
from .utils import get_offer_statistics

# Create your views here.


# Offer Management Views


@login_required(login_url="admin_login")
def category_offer_list(request):
    """Display list of all category offers with search and filter."""

    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("admin_login")

    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")

    offers = (
        CategoryOffer.objects.all().select_related("category").order_by("-created_at")
    )

    if search_query:
        offers = offers.filter(
            Q(name__icontains=search_query)  # offers name
            | Q(description__icontains=search_query)
            | Q(category__category_name__icontains=search_query)  # category name
        )

    if status_filter:
        offers = offers.filter(status=status_filter)

    paginator = Paginator(offers, 10)
    page_number = request.GET.get("page")
    offers_page = paginator.get_page(page_number)

    breadcrumbs = [{"label": "Back", "url": reverse("offer_dashboard")}]

    context = {
        "offers": offers_page,
        "search_query": search_query,
        "status_filter": status_filter,
        "breadcrumbs": breadcrumbs,
    }
    return render(request, "offers/category_offer_list.html", context)


@login_required(login_url="admin_login")
def add_category_offer(request):
    """create new category offer"""

    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("admin_login")

    categories = Category.objects.filter(is_listed=True).order_by("category_name")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        category_id = request.POST.get("category")
        discount = request.POST.get("discount", "").strip()
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        status = request.POST.get("status", "active")
        description = request.POST.get("description", "").strip()

        # Validation
        if not all([name, category_id, discount, start_date, end_date]):
            messages.error(request, "All required fields must be filled.")
            return render(
                request, "offers/add_category_offer.html", {"categories": categories}
            )

        try:
            discount = float(discount)
            if discount <= 0 or discount > 90:
                raise ValueError
        except ValueError:
            messages.error(request, "Discount must be between 0 and 90.")
            return render(
                request, "offers/add_category_offer.html", {"categories": categories}
            )

        # end date must be after start date
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
            if end < start:
                messages.error(request, "End must be after start date.")
                return render(
                    request,
                    "offers/add_category_offer.html",
                    {"categories": categories},
                )
        except ValueError:
            messages.error(request, "Invalid date format.")
            return render(
                request, "offers/add_category_offer.html", {"categories": categories}
            )

        # Create offer
        CategoryOffer.objects.create(
            name=name,
            category_id=category_id,
            discount=discount,
            start_date=start_date,
            end_date=end_date,
            status=status,
            description=description,
        )

        messages.success(request, f'Category offer "{name}" created successfully.')
        return redirect("category_offer_list")

    breadcrumbs = [{"label": "Back", "url": reverse("category_offer_list")}]

    context = {"categories": categories, "breadcrumbs": breadcrumbs}
    return render(request, "offers/add_category_offer.html", context)


@login_required(login_url="admin_login")
def edit_category_offer(request, offer_id):

    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("admin_login")

    offer = get_object_or_404(CategoryOffer, id=offer_id)
    categories = Category.objects.filter(is_listed=True).order_by("category_name")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        category_id = request.POST.get("category")
        discount = request.POST.get("discount", "").strip()
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        status = request.POST.get("status", "active")
        description = request.POST.get("description", "").strip()

        # Validation
        if not all([name, category_id, discount, start_date, end_date]):
            messages.error(request, "All required fields must be filled.")
            return render(
                request,
                "offers/edit_category_offer.html",
                {
                    "offer": offer,
                    "categories": categories,
                },
            )

        try:
            discount = float(discount)
            if discount <= 0 or discount > 90:
                raise ValueError
        except ValueError:
            messages.error(request, "Discount must be between 0 and 90.")
            return render(
                request,
                "offers/edit_category_offer.html",
                {
                    "offer": offer,
                    "categories": categories,
                },
            )

        # end date must be after start date
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
            if end < start:
                messages.error(request, "End must be after start date.")
                return render(
                    request,
                    "offers/add_category_offer.html",
                    {"categories": categories},
                )
        except ValueError:
            messages.error(request, "Invalid date format.")
            return render(
                request, "offers/add_category_offer.html", {"categories": categories}
            )

        # Update offer
        offer.name = name
        offer.category_id = category_id
        offer.discount = discount
        offer.start_date = start_date
        offer.end_date = end_date
        offer.status = status
        offer.description = description
        offer.save()

        messages.success(request, f'Offer "{name}" updated successfully.')
        return redirect("category_offer_list")

    breadcrumbs = [{"label": "Back", "url": reverse("category_offer_list")}]

    context = {
        "offer": offer,
        "categories": categories,
        "breadcrumbs": breadcrumbs,
    }
    return render(request, "offers/edit_category_offer.html", context)


@login_required(login_url="admin_login")
def delete_category_offer(request, offer_id):

    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect("admin_login")

    offer = get_object_or_404(CategoryOffer, id=offer_id)
    offer_name = offer.name
    offer.delete()

    messages.success(request, f'Offer "{offer_name}" deleted successfully.')
    return redirect("category_offer_list")


@login_required(login_url="admin_login")
def product_offer_list(request):
    """Dispay list of all product offers"""

    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")

    offers = (
        ProductOffer.objects.all().select_related("product").order_by("-created_at")
    )

    if search_query:
        offers = offers.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(product__product_name__icontains=search_query)
        )

    if status_filter:
        offers = offers.filter(status=status_filter)

    paginator = Paginator(offers, 10)
    page_number = request.GET.get("page")
    offer_page = paginator.get_page(page_number)

    breadcrumbs = [{"label": "Back", "url": reverse("offer_dashboard")}]

    context = {
        "offers": offer_page,
        "search_query": search_query,
        "status_filter": status_filter,
        "offer_type": "product",
        "breadcrumbs": breadcrumbs,
    }

    return render(request, "offers/product_offer_list.html", context)


@login_required(login_url="admin_login")
def add_product_offer(request):
    if not request.user.is_superuser:
        messages.error(request, "You don't have permission to access this page.")
        return redirect("admin_login")

    products = Product.objects.filter(is_listed=True).order_by("product_name")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        product_id = request.POST.get("product", "")
        discount = request.POST.get("discount", "").strip()
        start_date = request.POST.get("start_date", "")
        end_date = request.POST.get("end_date")
        status = request.POST.get("status", "active")
        description = request.POST.get("description", "").strip()

        if not all([name, product_id, discount, start_date, end_date]):
            messages.error(request, "All required fields must be filled.")
            return render(
                request, "offers/add_product_offre.html", {"products": products}
            )

        try:
            discount = float(discount)
            if discount <= 0 or discount > 90:
                raise ValueError
        except ValueError:
            messages.error(request, "Discount must be between ) and 90.")
            return render(
                request, "offers/add_product_offer.html", {"products": products}
            )

        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
            if end < start:
                messages.error(request, "End date must be after start date.")
                return render(
                    request, "offers/add_product_offer.html", {"products": products}
                )
        except ValueError:
            messages.error(request, f"Invalid date format.")
            return render(
                request, "offers/add_product_offer.html", {"products": products}
            )

        ProductOffer.objects.create(
            name=name,
            product_id=product_id,
            discount=discount,
            start_date=start_date,
            end_date=end_date,
            status=status,
            description=description,
        )

        messages.success(request, f'Product offer "{name}" created successfully.')
        return redirect("product_offer_list")

    breadcrumbs = [{"label": "Back", "url": reverse("product_offer_list")}]

    context = {"products": products, "breadcrumbs": breadcrumbs}
    return render(request, "offers/add_product_offer.html", context)


@login_required(login_url="admin_login")
def edit_product_offer(request, offer_id):

    if not request.user.is_superuser:
        messages.error(request, "You do not have the permission to accesss this page.")
        return redirect("admin_login")

    offer = get_object_or_404(ProductOffer, id=offer_id)
    products = Product.objects.filter(is_listed=True).order_by("product_name")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        product_id = request.POST.get("product", "")
        discount = request.POST.get("discount", "").strip()
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date", "")
        status = request.POST.get("status", "active")
        description = request.POST.get("description", "").strip()

        if not all([name, product_id, discount, start_date, end_date]):
            messages.error(request, "All required fields must be filled.")
            return render(
                request,
                "offers/edit_product_offer.html",
                {"offer": offer, "products": products},
            )

        try:
            discount = float(discount)
            if discount <= 0 or discount > 90:
                raise ValueError
        except ValueError:
            messages.error(request, "Discount must  be between 0 and 90.")
            return render(
                request,
                "offers/edit_product_offer.html",
                {"offer": offer, "products": products},
            )

        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
            if end_date < start_date:
                messages.error(request, "End date must be after start date.")
                return render(
                    request,
                    "offers/edit_product_offer.html",
                    {"offer": offer, "products": products},
                )
        except ValueError:
            messages.error(request, "Invalid date format.")
            return render(
                request,
                "offers/edit_product_offer.html",
                {"offer": offer, "products": products},
            )

        offer.name = name
        offer.product_id = product_id
        offer.discount = discount
        offer.start_date = start_date
        offer.end_date = end_date
        offer.status = status
        offer.description = description
        offer.save()

        messages.success(request, f'Product offer "{name}" updated successfully.')
        return redirect("product_offer_list")

    breadcrumbs = [{"label": "Back", "url": reverse("product_offer_list")}]

    context = {"offer": offer, "products": products, "breadcrumbs": breadcrumbs}
    return render(request, "offers/edit_product_offer.html", context)


@login_required(login_url="admin_login")
def delete_product_offer(request, offer_id):
    if not request.user.is_superuser:
        messages.error(request, "You do not have the permission to accesss this page.")
        return redirect("admin_login")

    offer = get_object_or_404(ProductOffer, id=offer_id)
    offer_name = offer.name
    offer.delete()
    messages.success(request, f'Product offer "{offer_name} deleted successfully."')
    return redirect("product_offer_list")


@login_required(login_url="admin_login")
def offer_dashboard(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have the permission to accesss this page.")
        return redirect("admin_login")

    stats = get_offer_statistics()

    # getmrecent offers for preview
    recent_category_offers = CategoryOffer.objects.all().order_by("-created_at")[:5]
    recent_product_offers = ProductOffer.objects.all().order_by("-created_at")[:5]

    context = {
        "stats": stats,
        "recent_category_offers": recent_category_offers,
        "recent_product_offers": recent_product_offers,
    }

    return render(request, "offers/dashboard.html", context)
