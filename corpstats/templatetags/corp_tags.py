from django import template
from django.utils.dateparse import parse_datetime

register = template.Library()

@register.filter(name='str2date')
def str2date(date_str):
    try:
        return parse_datetime(date_str)
    except:
        return date_str
