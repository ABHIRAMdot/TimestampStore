from .models import ReferralReward
from decimal import Decimal


def create_referral_reward(referrer, referred_user, reward_amount=Decimal("500.00")):
    """create a referral and credit wallet immediatly
    Returns:
        tuple: (success: bool, message: str, reward: ReferralReward or None)
    """

    # check the reward is already exists
    existing = ReferralReward.objects.filter(
        referrer=referrer, referred_user=referred_user
    ).first()

    if existing:
        return False, "Referral reward already exists for this user", None

    try:
        # create referral recod
        reward = ReferralReward.objects.create(
            referrer=referrer, referred_user=referred_user, reward_amount=reward_amount
        )

        # credit to wallet immediately calling credit_to_wallet_method in model
        success = reward.credit_to_wallet()

        if success:
            return True, f"₹{reward_amount} credited to wallet", reward
        else:
            return False, f"Failed to credit to wallet", reward
    except Exception as e:
        return False, f"Error createing reward: {str(e)}", None


# def get_user_referral_status(user):
#     """Get referral statistics for a user
#     RETURNS:
#     {
#         'total_referrals': 5,  # How many people referred
#         'total_earned': 2500,  # Total ₹ earned from referrals
#         'pending_rewards': 0,  # Rewards not yet credited (should be 0 always)
#         'recent_rewards': [...]  # Last 5 referral rewards
#     }
#     """

#     rewards = ReferralReward.objects.filter(referrer=user)

#     total_referrals = rewards.count()

#     total_earned = sum(reward.reward_amount for reward in rewards if reward.is_credited)

#     #count pending
#     pending_rewards = rewards.filter(is_credited=False).count()

#     recent_rewards = rewards.order_by('-created_at')[:5]

#     return {
#         'total_referrals': total_referrals,
#         'total_earned': total_earned,
#         'pending_rewards': pending_rewards,
#         'recent_rewards': recent_rewards,
#     }
