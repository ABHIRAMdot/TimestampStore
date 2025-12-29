from decimal import Decimal
from django.utils import timezone
from .models import ProductOffer, CategoryOffer

def get_best_offer_for_product(product):
    """Get the best offer (category offer , product offer)"""

    product_offer = ProductOffer.objects.filter(product=product, status='active').first()

    #get active category offer
    category_offer = None
    if product.category:
        category_offer = CategoryOffer.objects.filter(category=product.category, status='active').first()

    #check offers are active and not expired
    if product_offer and not product_offer.is_active:
        product_offer = None  #Ignore expired offer

    if category_offer and not category_offer.is_active:
        category_offer = None

    #no offer at all
    if not product_offer and not category_offer:
        return None
    
    #only product offer exists
    if product_offer and not category_offer:
        return {
            'offer_type': 'product',
            'offer': product_offer,
            'discount_percentage': product_offer.discount,
        }

    if category_offer and not product_offer:
        return {
            'offer_type': 'category',
            'offer': category_offer,
            'discount_percentage': category_offer.discount,
        }
    
    #if both offer exists choose larger discount
    if product_offer.discount >= category_offer.discount:
        return {
            'offer_type': 'product',
            'offer': product_offer,
            'discount_percentage': product_offer.discount,
        }
    else:
        return {
            'offer_type': 'category',
            'offer': category_offer,
            'discount_percentage': category_offer.discount,
        }
    
    

def calculate_discounted_price(original_price, discount_percentage):
    """calculate final price after applying percentage discount. """

    # Convert to Decimal for precision
    # str() wrapper ensures accurate conversion 
    original_price = Decimal(str(original_price))
    discount_percentage = Decimal(str(discount_percentage))

    discount_amount = original_price * (discount_percentage / 100) # eg: 1000 * (30/100)

    final_price = original_price - discount_amount

    #round the result to  2 decimal places
    return final_price.quantize(Decimal('0.01'))


def apply_offer_to_variant(variant):
    """Calculate complete pricing info for a product variant
    
    HOW IT WORKS:
    1. Get variant's product
    2. Check for best offer on that product
    3. Calculate discounted price
    4. Return all pricing info
    
    """

    product = variant.product

    #get variants original price
    original_price  = variant.price

    #check for offers on this product
    offer_info = get_best_offer_for_product(product)

    if not offer_info:
        return {
            'original_price': original_price,
            'discount_percentage': Decimal('0'),
            'discount_amount': Decimal('0'),
            'final_price': original_price,
            'offer_name': None,
            'offer_type': None,
            'has_offer': False    # to check in templates eg: {% if pricing.has_offer %}
        }
    
    # if offer exists calculate discount
    discount_percentage = offer_info['discount_percentage']
    final_price = calculate_discounted_price(original_price, discount_percentage)
    discount_amount = original_price - final_price

    return {
        'original_price': original_price,
        'discount_percentage': discount_percentage,
        'discount_amount': discount_amount,
        'final_price': final_price,
        'offer_name': offer_info['offer'],
        'offer_type': offer_info['offer_type'],
        'has_offer': True
    }




def get_offer_statistics():
    """Get overall offer statistics for admin dashboard.
    RETURNS:
    {
        'total_category_offers': 10,
        'active_category_offers': 5,
        'total_product_offers': 15,
        'active_product_offers': 8,
        'total_referral_rewards': 50,
        'total_referral_amount': 25000
    }
    """

    from django.db.models import Sum

    total_category = CategoryOffer.objects.count()
    active_category = CategoryOffer.objects.filter(status='active').count()

    total_product = ProductOffer.objects.count()
    active_product = ProductOffer.objects.filter(status='active').count()

    # referral_rewards = ReferralReward.objects.all()
    # total_referrals = referral_rewards.count()

    # total_referral_amount = referral_rewards.aggregate(total = Sum('reward_amount'))['total'] or 0

    return {
        'total_category_offers': total_category,
        'active_category_offers': active_category,
        'total_product_offers': total_product,
        'active_product_offers': active_product,
        # 'total_referral_rewards': total_referrals,
        # 'total_referral_amount': total_referral_amount,
    }
     

def expired_old_offers():
    """Mark expired offer as expired

    # management/commands/expire_offers.py
    from django.core.management.base import BaseCommand
    from offers.utils import expire_old_offers
    
    class Command(BaseCommand):
        def handle(self, *args, **options):
            count = expire_old_offers()
            print(f"Expired {count} offers")
    
    Run daily:
    python manage.py expire_offers
    
    Or add to crontab:
    0 0 * * * python manage.py expire_offers
    
    Returns:
        int: Number of offers expired

    """

    today = timezone.now().date()
    
    category_count = CategoryOffer.objects.filter(
        end_date__lt=today,
        status = 'active'
    ).update(status='expired')

    product_count = ProductOffer.objects.filter(
        end_date__lt=today,
        status='active'
    ).update(status='expired')

    return category_count + product_count


