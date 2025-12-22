from decimal import Decimal
from django.db import transaction
from .models import Coupon, CouponUsage


def validate_and_apply_coupon(coupon_code, user, cart_total):
    """
    Validate coupon  and calcualte discount
    returns:
    - Tuple: (success: bool, message: str, discount_amount: Decimal, coupon: Coupon or None)
    """

    coupon_code = coupon_code.strip().upper() #convert it to upper case

    #check if coupon exists
    try:
        coupon = Coupon.objects.get(code=coupon_code)
    except Coupon.DoesNotExist:
        return False, "Invalid coupon code", Decimal('0.00'), None
    
    #check coupon is valid
    is_valid, message = coupon.is_valid()
    if not is_valid:
        return False, message, Decimal('0.00'), None
    
    can_use, message = coupon.can_user_use(user)
    if not can_use:
        return False, message, Decimal('0.00'),None
    
    #check min purchase req
    if cart_total < coupon.min_purchase_amount:
        print("hey")
        return False, f"Minimum Purchase of ₹{coupon.min_purchase_amount} required to use this coupon.", Decimal('0.00'), None
    

    #calculate discount
    discount_amount, final_total = coupon.calculate_discount(cart_total)

    return True, "Coupon applied successfully!", discount_amount, coupon


def record_coupon_usage(coupon, user, order, discount_amount, cart_total_before_discount):
    """Record that a user used a coupon in an order"""

    try:
        with transaction.atomic():
            #create user record
            usage = CouponUsage.objects.create(
                coupon=coupon,
                user=user,
                order=order,
                discount_amount=discount_amount,
                cart_total_before_discount=cart_total_before_discount
            )

            #increment coupon usage counter
            coupon.times_used += 1
            coupon.save()
            
            return usage
    
    except Exception as e:
        print(f"error recording coupon usage: {e}")
        return None
    

def calculate_return_refund_with_coupon(order, items_to_return):
    """calculate refund amount when returning items from  order that used a coupon
        Distribute the coupon discount proportionally across all items
    """

    #check if order used a coupon
    try:
        coupon_usage = CouponUsage.objects.get(order=order)
        coupon_discount = coupon_usage.discount_amount
        original_order_total = coupon_usage.cart_total_before_discount
        coupon_used = True
        coupon_code = coupon_usage.coupon.code
    except CouponUsage.DoesNotExist:
        #no coupon used simple refund
        total_refund = Decimal('0.00')
        refund_details =[]

        for item in items_to_return:
            item_refund = item.price * item.quantity # just return what they paid
            total_refund += item_refund

            refund_details.append({
                'item': item,
                'item_price_paid':item_refund,
                'coupon_share': Decimal('0.00'),  #no coupon
                'refund_amount': item_refund
            })

        return {
            'total_refund': total_refund,
            'items_refund_details': refund_details,  # the list appended
            'coupon_used':False,
            'coupon_code': None
        }

    
    #coupon was used then calculate the proportion refund
    refund_details = []
    total_refund =Decimal('0.00')

    for item in  items_to_return:
        item_paid_total = item.price * item.quantity #from OrderItem model
        #calculate percentage of order( if 1000 is returning from 1500 and offer was 300 then 1000/1500 = 0.6667 (66.67% of the order is returning))
        item_percentage = item_paid_total / original_order_total

        #calculate this item's share of coupon discount(300 * 0.6667 = 200)
        item_coupon_share = coupon_discount * item_percentage
         
        #refund actually paid (original_price - coupon_share 1000 - 200)
        item_paid_price = item_paid_total - item_coupon_share

        refund_details.append({
            'item': item,
            'item_price_paid': item_paid_total,
            'coupon_share': item_coupon_share,
            'refund_amount': item_paid_price
        })

        total_refund += item_paid_price
    
    return {
        'total_refund': total_refund,
        'items_refund_details': refund_details,
        'coupon_used': True,
        'coupon_code': coupon_code
    }

def get_coupon_discount_for_display(order):
    """Get coupon info to display in order details"""

    try:
        usage = CouponUsage.objects.get(order=order)

        return{
            'has_coupon':True,
            'coupon_code': usage.coupon.code,
            'discount_amount': usage.discount_amount
        }
    except CouponUsage.DoesNotExist:
        return {
            'has_coupon':False,
            'coupon_code': None,
            'discount_amount': Decimal('0.00')
        }
