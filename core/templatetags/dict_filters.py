from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """Look up a key in a dictionary"""
    if dictionary is None:
        return []
    return dictionary.get(key, [])