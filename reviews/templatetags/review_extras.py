from django import template
from django.db import models

register = template.Library()


@register.filter
def dict_get(d, key):
    """Get a dictionary value using a dynamic key."""
    try:
        return d.get(int(key), 0)
    except:
        return 0


@register.filter
def div(a, b):
    """Divide two numbers safely."""
    try:
        return a / b if b else 0
    except:
        return 0


@register.filter
def mul(a, b):
    """Multiply two numbers."""
    try:
        return a * b
    except:
        return 0
