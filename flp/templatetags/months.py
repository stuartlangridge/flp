import calendar, datetime
from django import template

register = template.Library()

@register.filter
def month_name(month_number):
    return calendar.month_name[month_number]

@register.filter
def age(dt):
    if dt.tzinfo:
        now = datetime.datetime.now()
        now = now.replace(tzinfo=dt.tzinfo)
        diff = now - dt
    else:
        diff = datetime.datetime.now() - dt
    if diff.days > 0:
        return "%sd" % diff.days
    elif diff.seconds > 3600:
        return "%sh" % int(float(diff.seconds) / 3600)
    elif diff.seconds > 240:
        return "%sm" % int(float(diff.seconds) / 60)
    else:
        return "just now"