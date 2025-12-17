from datetime import timedelta
from django.utils import timezone

def get_date_range(filter_type, start_date=None, end_date=None):
    """Return start date and end date based on filter type"""

    today =  timezone.now().date()

    if filter_type == "week":
        start = today - timedelta(days=today.weekday())
        end = today

    elif filter_type == "day":
        start = today 
        end = today

    elif filter_type == "month":
        start = today.replace(day=1)
        end = today

    elif filter_type == "custom" and start_date and end_date:
        start = start_date
        end = end_date
    else:
        #fall back to this week
        start = today - timedelta(days=today.weekday())
        end = today

    return start, end
