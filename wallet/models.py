from django.db import models
from decimal import Decimal
from django.conf import settings

from accounts.models import Account
from orders.models import Order, OrderItem

# Create your models here.

class Wallet(models.Model):
    """One wallet per user, Stores current wallet"""
    user = models.OneToOneField(Account, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet for {self.user.email} - Balance: ₹{self.balance}"
    
    def has_balance(self, amount: Decimal) -> bool:
        return self.balance >= amount


class WalletTransaction(models.Model):
    """Tracks every change in wallet balance"""

    TRANSACTION_TYPES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),        
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')

    tx_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    old_balance = models.DecimalField(max_digits=10, decimal_places=2)
    new_balance = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True, null=True)

    #link to orde/ items
    order = models.ForeignKey(Order, on_delete=models.CASCADE,blank=True, null=True, related_name='Wallet_transactions')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE,blank=True, null=True, related_name='wallet_transactions')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.tx_type} - {self.amount} for {self.wallet.user.email}"
    