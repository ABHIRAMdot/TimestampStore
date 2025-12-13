import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
import csv
from django.urls import reverse


from wallet.models import Wallet

from .utils import get_or_create_wallet, credit_wallet
#imorting razorpay client
from payments.utils import razorpay_client

import logging
logger = logging.getLogger('project_logger')

# Create your views here.

@login_required(login_url='login')
def wallet_dashboard(request):
    """Show current wallet balance and recent transactions"""

    wallet = get_or_create_wallet(request.user)
    transactions = wallet.transactions.select_related('order', 'order_item') [:20]

    breadcrumbs = [
        {'label': 'Home', 'url': reverse('home')},
        {'label': 'Profile', 'url': reverse('profile')}
    ]


    context = {
        "wallet": wallet,
        "transactions":transactions,
        "breadcrumbs": breadcrumbs,
    }
    return render(request, 'wallet/wallet_dashboard.html',context)

@login_required(login_url='login')
def add_money_create_order(request):
    """Create a Razorpay order for  wallet reacharge."""

    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Invalid request method."}, status=405)

    try:
        data = json.loads(request.body)
        amount = Decimal(str(data.get('amount', 0)))
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"status": "error", "message": "Invalid amount."}, status=400)
    
    MIN_AMOUNT = Decimal('100.00')
    MAX_AMOUNT = Decimal('50000.00')

    if amount < MIN_AMOUNT:
        return JsonResponse({"status": "error", "message": f"Minimum amount is ₹{MIN_AMOUNT}."}, status=400)
    
    if amount > MAX_AMOUNT:
        return JsonResponse({"status": "error", "message": f"Maximum amount is ₹{MAX_AMOUNT}."}, status=400)
    
    user = request.user

    amount_paise = int(amount * 100)

    razorpay_data = {
        'amount': amount_paise,
        'currency': 'INR',
        # 'reciept': f"Wallet_{user.id}_{timezone.now().strftime("%Y%m%d%H%M%S")}",
        'payment_capture': 1
    }

    try:
        razorpay_order = razorpay_client.order.create(razorpay_data)
    except Exception as e:
        logger.error(f"Razorpay creation failed: {e}")
        return JsonResponse({
            "status": "error", 
            "message": "Failed to create payment order. Please try again."
        }, status=500)
    
    #store order info in session to verify this order id in verify payment view
    request.session['pending_wallet_recharge'] = {
        "razorpay_order_id": razorpay_order['id'],
        'amount':str(amount),   # Store as string to avoid Decimal serialization issues

    }
    request.session.modified = True

    return JsonResponse({
        "status": "success",
        "order_id": razorpay_order['id'],
        "amount": amount_paise,
        "key": settings.RAZORPAY_KEY_ID,
        "name": "Timestamp Store",
        "description": "Wallet Recharge"
    })

# verify razorpay payment and credit wallet
@csrf_exempt
@login_required(login_url='login')
@transaction.atomic
def add_money_verify_payment(request):
    """verify Razorpay payment signature and credit wallet."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid JSON."}, status=400)
    
    try: 
        data = json.loads(request.body)
        logger.info(f"Payment verification data:  {data}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)
    

    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_signature = data.get('razorpay_signature')

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        return JsonResponse({"status": "error", "message": " Missing payment details."}, status=400)
    
    #verify razorpay signature
    params = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }

    try:
        razorpay_client.utility.verify_payment_signature(params)
    except Exception as e:
        logger.error(f"Payment signature verification failed: {e}")
        return JsonResponse({"status": "error", "message": "Payment verification failed."}, status=400)
    
    # get pending recharge from session
    pending = request.session.get('pending_wallet_recharge')

    if not pending or pending.get('razorpay_order_id') != razorpay_order_id:
        return JsonResponse({"status": "error", "message": "No matching pending recharge found."}, status=400)
    
    amount = Decimal(pending['amount'])
    user = request.user

    #verify amount with razorpay
    try:
        rp_order = razorpay_client.order.fetch(razorpay_order_id)
        rp_amount = Decimal(rp_order['amount']) / 100        #convert to INR to check
    except Exception as e:
        logger.error(f"Failed to ferch razorpay order: {e}")
        return JsonResponse({"status": "error", "message": "Failed to verify payment amount"}, status=400)
    
    if rp_amount != amount:
        logger.error(f"Amount mismatch! Expected{amount},  but got {rp_amount}")
        return JsonResponse({"status": "error", "message": "Payment amount mismatch."}, status=400)
    
    #credit-wallet for automatic balance update , transaction record and error handling
    description = f"Wallet recharged via Razorpay (Payment ID: {razorpay_payment_id})"
    wallet = credit_wallet(
        user=user,
        amount=amount,
        tx_type='credit',
        description=description,
        order=None,
        order_item=None
    )

    if not wallet:
        logger.error(f"Wallet credit failed for user {user.id}")
        return JsonResponse({"status": "error", "message": "Failed to credit wallet."}, status=500)
    
    if 'pending_wallet_recharge' in request.session:
        del request.session['pending_wallet_recharge']
    
    logger.info(f"Wallet recharged : User {user.id}, Amount ₹{amount}")

    return JsonResponse({"status": "success", "message": f"₹{amount} added to your wallet successfully!", 
                         "new_balance": str(wallet.balance)})

    

@login_required(login_url='admin_login')
def admin_wallet_view(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')        
        return redirect('admin_login')
    
    search_query = request.GET.get('search', "").strip()
    filter_value = request.GET.get('filter', "").strip()

    wallets = Wallet.objects.select_related('user').exclude(user__is_superuser=True).order_by('-created_at')

    if search_query:
        
        wallets = wallets.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )
    
    
    #filter
    if filter_value == "high_balance":
        wallets = wallets.order_by("-balance")
    elif filter_value == "low_balance":
        wallets = wallets.order_by("balance")
    else:
        wallets = wallets.order_by("-created_at")


    # #  EXPORT TO CSV
    # if request.GET.get("export") == "csv":
    #     return export_wallet_csv(wallets)



    paginator = Paginator(wallets,10)
    page_number = request.GET.get('page')
    wallets = paginator.get_page(page_number)

    context = {
        'wallets': wallets,
        'search_query': search_query,
        'filter_value': filter_value,
        
        }

    return render(request, 'admin/admin_wallet_view.html', context)


# def export_wallet_csv(wallets):
#     response = HttpResponse(content_type='text/csv')
#     response['Content-Disposition'] = 'attachment; filename="wallets.csv"'

#     writer = csv.writer(response)
#     writer.writerow(["User", "Email", "Balance", "Updated At"])

#     for w in wallets:
#         writer.writerow([
#             f"{w.user.first_name} {w.user.last_name}",
#             w.user.email,
#             w.balance,
#             w.updated_at.strftime("%d-%m-%Y %H:%M")
#         ])

#     return response

@login_required(login_url='admin_login')
def admin_wallet_history(request, wallet_id):

    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page' )
        return redirect('admin_login')
    
    wallet = get_object_or_404(Wallet, id=wallet_id)
    transactions = wallet.transactions.order_by('-created_at')

    paginator = Paginator(transactions, 10)
    page_number = request.GET.get('page')
    transactions = paginator.get_page(page_number)

    start_index = transactions.start_index()

    breadcrumbs = [
        {"label": "Wallet", "url": reverse("admin_wallet_view")},
        
    ]

    context = {
        'wallet': wallet,
        'transactions': transactions,
        'start_index': start_index,
        'breadcrumbs': breadcrumbs,
        
    }
    
    return render(request, 'admin/admin_wallet_history.html', context)
