from datetime import timedelta, datetime
from django.utils import timezone
from django.db.models import Sum, Count, F
from decimal import Decimal

from orders.models import Order, OrderItem
from products.models import Product
from category.models import Category

def get_date_range(filter_type, start_date=None, end_date=None):
    """Return start date and end date based on filter type"""

    today =  timezone.now().date()

    if filter_type == "today":
        #both start and end are the same
        return today, today

    elif filter_type == "week":
        day_since_monday = today.weekday()         # weekday() returns 0 for Monday, 6 for Sunday
        monday = today - timedelta(days=day_since_monday)
        return monday, today


    elif filter_type == "month":
        first_day_of_month = today.replace(day=1)        # replace(day=1) changes any date to 1st of that month
        return first_day_of_month, today
    
    elif filter_type == 'year':
        jan_first = today.replace(month=1, day=1)
        return jan_first, today

    elif filter_type == "custom" and start_date and end_date:
        return start_date, end_date

    #fall back to this week(last 7 days)
    seven_days_ago = today - timedelta(days=7)
    return seven_days_ago, today


def get_valid_orders(start, end):
    """Get all orders that cout as sales(not cancelled, not returned)"""

    # get valid orders (exclude cancelled, returned,..)
    valid_statuses = ['confirmed', 'processing', 'shipped', 'out_for_delivery', 'delivered']

    orders = Order.objects.filter(
        created_at__date__range=[start, end],
        status__in=valid_statuses
    )

    return orders



#cahrt data
def get_chart_data(filter_type, start_date=None, end_date=None):
    """Get data for the sales chart """

    # # # get valid orders (exclude cancelled, returned,..)
    # valid_statuses = ['confirmed', 'processing', 'shipped', 'out_for_delivery', 'delivered']

    # orders = Order.objects.filter(
    #     created_at__date__range=[start, end], # only orders in the date range
    #     status__in=valid_statuses
    # )


    orders = get_valid_orders(start_date, end_date)

    if filter_type == 'today':
        #lists for 24 hours
        labels = []
        sales = [0] * 24
        order_counts = [0] * 24

        # Create labels (00:00, 01:00, ..., 23:00)
        for i in range(24):
            labels.append(f"{i:02d}:00")  # adds leading zero(01 not 1)

        for order in orders:
            hour =  order.created_at.hour   #get hour(0-23)
            # Add sales amount for this hour
            sales[hour] += float(order.total_amount)
            #count orders for this hour
            order_counts[hour] += 1


    
    elif filter_type == 'week':
        labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

        sales_by_day = {day: 0 for day in labels}
        orders_by_day = {day: 0 for day in labels}

        # Loop through all orders and group by day name
        for order in orders:
            day_name = order.created_at.strftime('%a')  # 'Mon', 'Tue',..
            sales_by_day[day_name] += float(order.total_amount)
            orders_by_day[day_name] += 1

        
        sales = []
        order_counts = []
        for label in labels:
            sales.append(sales_by_day.get(label, 0))
            order_counts.append(orders_by_day.get(label, 0))

    
    elif filter_type == 'month':
        # calculate how many days to show
        days_count = (end_date - start_date).days + 1

        labels = []
        for i in range(days_count):
            day = start_date + timedelta(days=i)
            labels.append(day.strftime('%d'))  # '01' , '02',..
        
        sales_by_date = {date: 0 for date in labels}
        orders_by_date = {date: 0 for date in labels}

        # count sales and orders
        for order in orders:
            date_str = order.created_at.strftime('%d')
            if date_str in sales_by_date:
                sales_by_date[date_str] += float(order.total_amount)
                orders_by_date[date_str] += 1
            
        sales = []
        order_counts = []
        for label in labels:
            sales.append(sales_by_date.get(label, 0))
            order_counts.append(orders_by_date.get(label, 0))

    
    elif filter_type == 'year':
        labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        

        sales_by_month = {month: 0 for month in labels}
        order_by_month = {month: 0 for month in labels}

        for order in orders:
            month_name = order.created_at.strftime('%b')  # jan, feb,..
            sales_by_month[month_name] += float(order.total_amount)
            order_by_month[month_name] += 1
        
        sales = []
        order_counts = []
        for label in labels:
            sales.append(sales_by_month.get(label, 0))
            order_counts.append(order_by_month.get(label, 0))

    
    else:

        # custom date
        days_count = (end_date - start_date).days + 1

        labels = []
        for i in range(days_count):
            day = start_date + timedelta(days=i)
            labels.append(day.strftime('%d/%m'))   #'22/12' , '23/12', ..

        
        sales_by_date = {date: 0 for date in labels}
        orders_by_date = {date: 0 for date in labels}

        for order in orders:
            date_str = order.created_at.strftime('%d/%m')
            if date_str in sales_by_date:
                sales_by_date[date_str] += float(order.total_amount)
                orders_by_date[date_str] += 1

        sales = []
        order_counts = []
        for label in labels:
            sales.append(sales_by_date.get(label, 0))
            order_counts.append(orders_by_date.get(label, 0))


    return {
        'labels': labels,
        'sales': sales,
        'orders': order_counts
    }
    


def get_statistics(start_date, end_date):
    """Calculate the total orders,revenue, sales, average """

    orders = get_valid_orders(start_date, end_date)

    results = orders.aggregate(
        total_orders=Count('id'),
        total_revenue=Sum('total_amount'),
        total_products=Sum('items__quantity')
    )

    total_orders = results['total_orders'] or 0
    total_revenue = float(results['total_revenue'] or 0)
    total_products = results['total_products'] or 0

    #calculate average (avoid divide by zero)
    if total_orders > 0:
        avg_order_value = total_revenue / total_orders
    else:
        avg_order_value = 0

    return {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_products_sold': total_products,
        'average_order_value': avg_order_value
    }


# best selling products
def get_best_products(start_date, end_date, limit=10):
    """Find top 10 products by quantity sold"""

    valid_statuses = ['confirmed', 'processing', 'shipped', 'out_for_delivery', 'delivered']

    #get all order items in date range
    items = OrderItem.objects.filter(
        order__created_at__date__range=[start_date, end_date],
        order__status__in=valid_statuses,
        status__in=valid_statuses
    )

    products = items.values(
        'product__id',
        'product__product_name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum(F('price') * F('quantity'))
    ).order_by('-total_quantity')[:limit]

    #formating the result
    result = []
    for item in products:
        try:
            product = Product.objects.get(id=item['product__id'])
            result.append({
                'product': product,
                'total_quantity': item['total_quantity'],
                'total_revenue': float(item['total_revenue'] or 0)
            })
        except Product.DoesNotExist:
            continue
    return result


def get_best_categories(start_date, end_date, limit=10):
    """Find 10 categories by quantity sold"""

    valid_statuses = ['confirmed', 'processing', 'shipped', 'out_for_delivery', 'delivered']

    #get order items with categories
    items  = OrderItem.objects.filter(
        order__created_at__date__range=[start_date, end_date],
        order__status__in=valid_statuses,
        status__in=valid_statuses,
        product__category__isnull=False  #only items with acategory
    )

    categories = items.values('product__category__id', 'product__category__category_name'
                              ).annotate(
                                  total_quantity=Sum('quantity'),
                                  total_revenue=Sum(F('price') * F('quantity')),
                                  product_count=Count('product__id', distinct=True)
                              ).order_by('-total_quantity')[:limit]
    

    result = []
    for item in categories:
        try:
            category = Category.objects.get(id=item['product__category__id'])
            result.append({
                'category': category,
                'total_quantity': item['total_quantity'],
                'total_revenue': float(item['total_revenue'] or 0),
                'product_count': item['product_count']
            })
        except Category.DoesNotExist:
            continue
    
    return result

