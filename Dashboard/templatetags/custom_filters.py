from django import template
import time

register = template.Library()

@register.filter
def time_ago(timestamp):
    if not timestamp:
        return ""
    
    try:
        # Convert timestamp to integer just in case
        timestamp = int(timestamp)
        now = int(time.time())
        diff = now - timestamp

        if diff < 60:
            return "Just now"
        elif diff < 3600:
            minutes = diff // 60
            return f"{minutes} min{'s' if minutes > 1 else ''} ago"
        elif diff < 86400:
            hours = diff // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff < 604800:
            days = diff // 86400
            return f"{days} day{'s' if days > 1 else ''} ago"
        else:
            # Fallback for very old dates
            import datetime
            return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
            
    except (ValueError, TypeError):
        return timestamp