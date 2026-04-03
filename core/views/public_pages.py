# views/public_pages.py
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.conf import settings
import json
import logging

logger = logging.getLogger(__name__)

def sms_opt_in(request):
    """Public SMS opt-in consent page for Twilio verification"""
    return render(request, 'core/sms_opt_in.html')

def privacy_policy(request):
    """Public privacy policy page"""
    return render(request, 'core/privacy_policy.html')

def terms_of_service(request):
    """Public terms of service page"""
    return render(request, 'core/terms_of_service.html')


def public_home(request):
    if request.user.is_authenticated:
        return redirect('operations_hub')
    return render(request, 'core/public_home.html')


@csrf_exempt
@require_POST
def submit_contact_form(request):
    """Handle public contact form submission — sends email to fishteckorders@gmail.com"""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        company = data.get('company', '').strip()
        email = data.get('email', '').strip()
        message = data.get('message', '').strip()

        if not name or not email:
            return JsonResponse({'error': 'Name and email are required'}, status=400)

        send_mail(
            subject=f'FishTeck Contact Form — {name}' + (f' ({company})' if company else ''),
            message=f'Name: {name}\nCompany: {company}\nEmail: {email}\n\nMessage:\n{message}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['fishteckorders@gmail.com'],
            fail_silently=False,
        )
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Contact form error: {e}")
        return JsonResponse({'error': 'Failed to send message. Please try again.'}, status=500)