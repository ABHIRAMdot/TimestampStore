from decimal import Decimal
from django.db import transaction

from accounts.models import Account
from .models import Wallet, WalletTransaction


def get_or_create_wallet(user: Account) -> Wallet:  #It accepts one argument: user (type: Account model).  -> Wallet means this function will return a Wallet object.
    """
    Always use this to access a wallet.
    If wallet does not exist, it will be created with 0 balance.
    """
    wallet, created = Wallet.objects.get_or_create(user=user, defaults={'balance': Decimal('0.00')})
    
    return wallet

@transaction.atomic
def credit_wallet(
    user: Account,
    amount: Decimal,
    tx_type:str,
    description:str = "",
    order=None,
    order_item=None,


):
    """Add money to wallet and create a transaction record."""
    
    amount = Decimal(str(amount))
    if amount <= 0:
        return None 
    
    wallet = get_or_create_wallet(user)

    old_balance = wallet.balance
    new_balance = old_balance + amount

    wallet.balance = new_balance
    wallet.save()

    WalletTransaction.objects.create(
        wallet=wallet,
        tx_type=tx_type,
        amount=amount,
        old_balance=old_balance,
        new_balance=new_balance,
        description=description,
        order=order,
        order_item=order_item,
    )

    return wallet


@transaction.atomic
def debit_wallet(
    user:Account,
    amount:Decimal,
    tx_type:str,
    description:str = "",
    order=None,
    order_item=None,


):
    """
    Remove money from wallet (for order payments etc).
    Returns (success, message).
    """

    amount = Decimal(str(amount))
    if amount <= 0:
        return False, "Amount must be positive."
    
    wallet = get_or_create_wallet(user)

    if wallet.balance < amount:
        return False, "Insufficient wallet balance."
    
    old_balance = wallet.balance
    new_balance = old_balance - amount

    wallet.balance = new_balance
    wallet.save()

    WalletTransaction.objects.create(
        wallet=wallet,
        tx_type=tx_type,
        amount=amount,
        old_balance=old_balance,
        new_balance=new_balance,
        description=description,
        order=order,
        order_item=order_item,
    )

    return True, "Wallet debitted successfuly."