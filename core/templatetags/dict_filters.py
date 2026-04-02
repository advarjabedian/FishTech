from django import template
import json

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """Look up a key in a dictionary"""
    if dictionary is None:
        return []
    return dictionary.get(key, [])


@register.filter
def lead_json(lead):
    """Serialize a Lead object to JSON for inline JS"""
    return json.dumps({
        'company_name': lead.company_name,
        'contact_name': lead.contact_name,
        'contact_email': lead.contact_email,
        'contact_phone': lead.contact_phone,
        'stage': lead.stage,
        'contract_value': str(lead.contract_value) if lead.contract_value else '',
        'last_contacted': lead.last_contacted.isoformat() if lead.last_contacted else '',
        'next_followup': lead.next_followup.isoformat() if lead.next_followup else '',
        'notes': lead.notes,
    })