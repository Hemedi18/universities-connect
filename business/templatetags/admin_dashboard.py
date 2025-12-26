from django import template
from django.db.models import Count
from django.db.models.functions import TruncDay
from django.utils import timezone
from datetime import timedelta
from business.models import Item

# Register the template tag library
register = template.Library()

@register.simple_tag
def get_daily_stats():
    # Get data for the last 30 days
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    # Query items created per day
    daily_items = Item.objects.filter(
        created_at__gte=start_date
    ).annotate(
        date=TruncDay('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Prepare data for Chart.js
    labels = []
    data = []
    
    # Create a dict for easy lookup
    stats_dict = {item['date'].strftime('%Y-%m-%d'): item['count'] for item in daily_items}
    
    # Fill in missing days with 0
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        labels.append(date_str)
        data.append(stats_dict.get(date_str, 0))
        current_date += timedelta(days=1)
        
    return {
        'labels': labels,
        'data': data,
    }