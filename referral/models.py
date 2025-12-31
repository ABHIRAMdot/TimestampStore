from django.db import models
from wallet.utils import credit_wallet

# Create your models here.


class ReferralReward(models.Model):
    """wallet credit to users who refer others.

        HOW IT WORKS:
    1. User A shares referral code with User B
    2. User B registers using code
    3. User A automatically gets ₹500 coupon
    4. User A can use coupon on next purchase

    """

    code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    referrer = models.ForeignKey(
        "accounts.Account",  # String reference to avoid cercular import
        on_delete=models.CASCADE,
        related_name="referral_reward_given",
        help_text=" user who referred someone",
    )  # User who referred

    referred_user = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="referred_by_reward",
        help_text="User who was referred",
    )  # User who was referred

    reward_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=500.00,
        help_text="Amount credited to referrer's wallet (in rupees)",
    )

    is_credited = models.BooleanField(
        default=False, help_text="Has the reward been credited to wallet?"
    )
    credited_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

        # One user can only be referred once
        unique_together = [["referrer", "referred_user"]]

    def __str__(self):
        return f"{self.referrer.email} -> {self.referred_user.email} (₹{self.reward_amount})"

    def credit_to_wallet(self):
        """Credit reward amount to referrer's wallet.

        RETURNS:
        - True if successful
        - False if already credited or error
        """
        # prevent double crediting
        if self.is_credited:
            return False

        try:
            # credit wallet and create transaction record
            credit_wallet(
                user=self.referrer,
                amount=self.reward_amount,
                tx_type="credit",
                description=f"Referral reward: {self.referred_user.email} joined using your code",
                order=None,
                order_item=None,
            )

            self.is_credited = True
            self.credited_at = timezone.now()
            self.save()

            return True
        except Exception as e:
            logging.error("Error crediting referral reward: {e}")
            return False

    @property
    def status(self):
        """Get status of reward"""
        return "Credited" if self.is_credited else "Pending"
