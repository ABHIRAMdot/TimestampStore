from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Exists, OuterRef
from datetime import date
from decimal import Decimal, InvalidOperation
from django.utils import timezone

from .models import Coupon, CouponUsage

# Create your views here.


@login_required(login_url="admin_login")
def coupon_list(request):
    """Display all coupons"""

    if not request.user.is_superuser:
        messages.error(request, "You don't have permission to access this page")
        return redirect("admin_login")

    search_query = request.GET.get("search", "").strip()
    status_filter = request.GET.get("status", "").strip()

    coupons = Coupon.objects.all().order_by("-created_at")

    if search_query:
        coupons = coupons.filter(
            Q(code__icontains=search_query) | Q(description__icontains=search_query)
        )

    if status_filter == "active":
        coupons = coupons.filter(is_active=True)
    elif status_filter == "inactive":
        coupons = coupons.filter(is_active=False)

    paginator = Paginator(coupons, 5)
    page_number = request.GET.get("page")
    coupons_page = paginator.get_page(page_number)

    context = {
        "coupons": coupons_page,
        "search_query": search_query,
        "status_filter": status_filter,
    }

    return render(request, "coupons/coupon_list.html", context)


@login_required(login_url="admin_login")
def add_coupon(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("admin_login")

    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        description = request.POST.get("description", "").strip()

        discount_type = request.POST.get("discount_type", "fixed")

        discount_amount = request.POST.get("discount_amount", "").strip()
        discount_percentage = request.POST.get("discount_percentage", "").strip()
        min_purchase_amount = request.POST.get("min_purchase_amount", "0").strip()
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        usage_limit = request.POST.get("usage_limit", "").strip()
        one_time_use = request.POST.get("one_time_use") == "on"
        is_active = request.POST.get("is_active") == "on"

        if not all([code, start_date, end_date]):
            messages.error(request, "Please fill all required fileds.")
            return render(request, "coupons/add_coupon.html")

        if Coupon.objects.filter(code=code).exists():
            messages.error(request, f"Coupon code'{code}' already exists.")
            return render(request, "coupons/add_coupon.html")

        # validate based on type
        if discount_type == "fixed":
            if not discount_amount:
                messages.error(
                    request, "Discount amount is required for FIXED coupons."
                )
                return render(request, "coupons/add_coupon.html")

            # discount amount validation
            try:
                discount_amount = Decimal(discount_amount)
                if discount_amount <= 0:
                    raise ValueError
            except (ValueError, InvalidOperation):
                messages.error(request, "Please enter a valid discount amount.")
                return render(request, "coupons/add_coupon.html")

            discount_percentage_value = None  # not used
        else:

            if not discount_percentage:
                messages.error(request, "Discount percentage is required.")
                return render(request, "coupons/add_coupon.html")

            try:
                discount_percentage_value = Decimal(discount_percentage)
                if not (1 <= discount_percentage_value <= 90):
                    raise ValueError
            except (ValueError, InvalidOperation):
                messages.error(
                    request, "Invalid percentage (must be between 1 and 90)."
                )
                return render(request, "coupons/add_coupon.html")

            discount_amount = Decimal("0.00")  # not user only percentage

        # minimum purchase
        try:
            min_purchase = Decimal(min_purchase_amount)
            if min_purchase < 0:
                raise ValueError
        except (ValueError, InvalidOperation):
            messages.error(request, "Pleaese enter a valid minimum purchase amount.")
            return render(request, "coupons/add_coupon.html")

        # date validation
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
            if end < start:
                messages.error(request, "End date must be after start date.")
                return render(request, "coupons/add_coupon.html")
        except ValueError:
            messages.error(request, "Invalid date format.")
            return render(request, "coupons/add_coupon.html")

        # validate usage limit
        usage_limit_value = None
        if usage_limit:
            try:
                usage_limit_value = int(usage_limit)
                if usage_limit_value <= 0:
                    raise ValueError
            except ValueError:
                messages.error(request, "Please enter a valid usage limit.")
                return render(request, "coupons/add_coupon.html")

        # create coupon
        try:
            coupon = Coupon.objects.create(
                code=code,
                description=description,
                discount_type=discount_type,
                discount_amount=discount_amount,
                discount_percentage=discount_percentage_value,
                min_purchase_amount=min_purchase,
                start_date=start_date,
                end_date=end_date,
                usage_limit=usage_limit_value,
                one_time_use=one_time_use,
                is_active=is_active,
            )
            messages.success(request, f"Coupon '{code}' created successfully.")
            return redirect("coupon_list")
        except Exception as e:
            messages.error(request, f"Error creating coupon: {str(e)}")
            return render(request, "coupons/add_coupon.html")

    context = {"today": date.today().isoformat()}
    return render(request, "coupons/add_coupon.html", context)


@login_required(login_url="admin_login")
def edit_coupon(request, coupon_id):
    if not request.user.is_superuser:
        messages.error(request, "You do not have the permission to access this page.")
        return redirect("admin_login")

    coupon = get_object_or_404(Coupon, id=coupon_id)

    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        description = request.POST.get("description", "").strip()

        discount_type = request.POST.get("discount_type", coupon.discount_type)
        discount_amount = request.POST.get("discount_amount", "").strip()
        discount_percentage = request.POST.get("discount_percentage", "").strip()

        min_purchase_amount = request.POST.get("min_purchase_amount", "0").strip()
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        usage_limit = request.POST.get("usage_limit", "").strip()
        one_time_use = request.POST.get("one_time_use") == "on"
        is_active = request.POST.get("is_active") == "on"

        if not all([code, start_date, end_date]):
            messages.error(request, "Please fill all required fileds.")
            return render(request, "coupons/edit_coupon.html", {"coupon": coupon})

        if Coupon.objects.filter(code=code).exclude(id=coupon_id).exists():
            messages.error(request, f"Coupon code'{code}' already exists.")
            return render(request, "coupons/edit_coupon.html", {"coupon": coupon})

        if discount_type == "fixed":
            if not discount_amount:
                messages.error(
                    request, "Discount amount is required for  fixed coupons."
                )
                return render(request, "coupons/edit_coupon.html", {"coupon": coupon})

            # discount amount validation
            try:
                discount_amount_value = Decimal(discount_amount)
                if discount_amount_value <= 0:
                    raise ValueError
            except (ValueError, InvalidOperation):
                messages.error(request, "Please enter a valid discount amount.")
                return render(request, "coupons/edit_coupon.html", {"coupon": coupon})

            discount_percentage_value = None

        else:
            # VALIDATE PERCENTAGE
            if not discount_percentage:
                messages.error(request, "Discount percentage is required.")
                return render(request, "coupons/edit_coupon.html", {"coupon": coupon})

            try:
                discount_percentage_value = Decimal(discount_percentage)
                if not (1 <= discount_percentage_value <= 90):
                    raise ValueError
            except (ValueError, InvalidOperation):
                messages.error(request, "Percentage must be between 1 and 90.")
                return render(request, "coupons/edit_coupon.html", {"coupon": coupon})

            discount_amount_value = Decimal("0.00")  # unused

        # minimum purchase
        try:
            min_purchase = Decimal(min_purchase_amount)
            if min_purchase < 0:
                raise ValueError
        except (ValueError, InvalidOperation):
            messages.error(request, "Pleaese enter a valid minimum purchase amount.")
            return render(request, "coupons/edit_coupon.html", {"coupon": coupon})

        # date validation
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
            if end < start:
                messages.error(request, "End date must be after start date.")
                return render(request, "coupons/edit_coupon.html", {"coupon": coupon})
        except ValueError:
            messages.error(request, "Invalid date format.")
            return render(request, "coupons/edit_coupon.html", {"coupon": coupon})

        # validate usage limit
        usage_limit_value = None
        if usage_limit:
            try:
                usage_limit_value = int(usage_limit)
                if usage_limit_value <= 0:
                    raise ValueError
            except ValueError:
                messages.error(request, "Please enter a valid usage limit.")
                return render(request, "coupons/edit_coupon.html", {"coupon": coupon})

        try:
            coupon.code = code
            coupon.description = description

            coupon.discount_type = discount_type
            coupon.discount_amount = discount_amount_value
            coupon.discount_percentage = discount_percentage_value

            coupon.min_purchase_amount = min_purchase
            coupon.start_date = start
            coupon.end_date = end
            coupon.usage_limit = usage_limit_value
            coupon.one_time_use = one_time_use
            coupon.is_active = is_active
            coupon.save()

            messages.success(request, f'Coupon "{code}" updated successfully!')
            return redirect("coupon_list")

        except Exception as e:
            messages.error(request, f"Error updating coupon: {str(e)}")
            return render(request, "coupons/edit_coupon.html", {"coupon": coupon})

    context = {"coupon": coupon}
    return render(request, "coupons/edit_coupon.html", context)


@login_required(login_url="admin_login")
def delete_coupon(request, coupon_id):
    if not request.user.is_superuser:
        messages.error(request, "You do no have the permission to perform this action.")
        return redirect("admin_login")

    coupon = get_object_or_404(Coupon, id=coupon_id)
    code = coupon.code

    # check if coupon has been used
    usage_count = coupon.usages.count()

    if usage_count > 0:
        messages.warning(
            request,
            f"Coupon '{code}' has been used {usage_count} times"
            "Conside deactivaring instead of deleting.",
        )
        return redirect("coupon_list")

    coupon.delete()
    messages.success(request, f"Coupon '{code}' deleted successfully.")
    return redirect("coupon_list")


# TOGGLE COUPON STATUS
@login_required(login_url="admin_login")
def toggle_coupon_status(request, coupon_id):
    """Activate/deactivate a coupon"""

    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect("admin_login")

    coupon = get_object_or_404(Coupon, id=coupon_id)

    coupon.is_active = not coupon.is_active
    coupon.save()

    status = "activated" if coupon.is_active else "deactivated"
    messages.success(request, f'Coupon "{coupon.code}" {status} successfully.')

    return redirect("coupon_list")


# COUPON USAGE HISTORY
@login_required(login_url="admin_login")
def coupon_usage_history(request, coupon_id):
    """View all usage history for a specific coupon"""

    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("admin_login")

    coupon = get_object_or_404(Coupon, id=coupon_id)

    usages = (
        CouponUsage.objects.filter(coupon=coupon)
        .select_related("user", "order")
        .order_by("-used_at")
    )

    # Calculate total discount given
    total_discount = usages.aggregate(total=Sum("discount_amount"))["total"] or Decimal(
        "0.00"
    )

    paginator = Paginator(usages, 20)
    page_number = request.GET.get("page")
    usages_page = paginator.get_page(page_number)

    context = {
        "coupon": coupon,
        "usages": usages_page,
        "total_discount": total_discount,
    }

    return render(request, "coupons/usage_history.html", context)


@login_required(login_url="login")
def user_available_coupons(request):

    today = timezone.now().date()

    # get all active coupon that are valid today
    coupons = Coupon.objects.filter(
        is_active=True, start_date__lte=today, end_date__gte=today
    ).order_by("-discount_amount")

    # annotate each coupon with whether the user has already ued it
    coupons = coupons.annotate(
        user_has_used=Exists(
            CouponUsage.objects.filter(coupon=OuterRef("pk"), user=request.user)
        )
    )

    # further filter based on usage limits
    available_coupons = []
    used_coupons = []

    for coupon in coupons:
        # check total usage limit reached
        if coupon.usage_limit and coupon.times_used >= coupon.usage_limit:
            continue

        # check alresdy used
        if coupon.one_time_use and coupon.user_has_used:
            used_coupons.append(coupon)
        else:
            available_coupons.append(coupon)

    context = {
        "available_coupons": available_coupons,
        "used_coupons": used_coupons,
    }

    return render(request, "coupons/user_coupons.html", context)


@login_required(login_url="login")
def user_coupon_usage_history(request):
    usages = (
        CouponUsage.objects.filter(user=request.user)
        .select_related("coupon", "order")
        .order_by("-used_at")
    )

    # calculate total savings
    total_savings = sum(usage.discount_amount for usage in usages)

    context = {
        "usages": usages,
        "total_savings": total_savings,
    }

    return render(request, "coupons/user_coupons_history.html", context)
