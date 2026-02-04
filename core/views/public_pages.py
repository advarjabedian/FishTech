# views/public_pages.py
from django.shortcuts import render

def sms_opt_in(request):
    """Public SMS opt-in consent page for Twilio verification"""
    return render(request, 'core/sms_opt_in.html')

def privacy_policy(request):
    """Public privacy policy page"""
    return render(request, 'core/privacy_policy.html')

def terms_of_service(request):
    """Public terms of service page"""
    return render(request, 'core/terms_of_service.html')