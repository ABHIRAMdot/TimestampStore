from django.shortcuts import render, redirect
# from django.contrib import messages
# from django.contrib.auth.decorators import login_required
# from django.core.paginator import Paginator
# from django.db.models import Q


# from .models import ReferralReward

# # Create your views here.



# @login_required(login_url='admin_login')
# def referral_reward_list(request):
#     if not request.user.is_superuser:
#         messages.error(request, 'You do not have the permission to accesss this page.')
#         return redirect('admin_login')
    
#     search_query = request.POST.get('search', '').strip()
#     status_filter = request.POST.get('status', '').strip()

#     rewards = ReferralReward.objects.all().select_related('referrer', 'referred_user').order_by('-created_at')

#     if search_query:
#         rewards = rewards.filter(
#             Q(referrer__email__icontains=search_query) |
#             Q(referred_user__email__icontains=search_query)
#         )

#     if status_filter == 'credited':
#         rewards = rewards.filter(is_credited=True)
#     elif status_filter == 'pending':
#         rewards = rewards.filter(is_credited=False)

#     paginator = Paginator(rewards, 10)
#     page_number = request.GET.get('page')
#     rewards_page = paginator.get_page(page_number)

#     context ={
#         'rewards': rewards_page,
#         'search_query': search_query,
#         'status_filter': status_filter,

#     }
#     return render(request, 'offers/referral_reward_list.html', context)