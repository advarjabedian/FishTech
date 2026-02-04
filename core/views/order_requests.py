from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from ..models import InboundMessage, User, Tenant, get_current_tenant
import json
import logging
import os

logger = logging.getLogger(__name__)


def get_email_settings_api(request):
    """Get current email settings for tenant"""
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)
    
    return JsonResponse({
        'success': True,
        'email_address': tenant.inbound_email_address or '',
        'imap_server': tenant.inbound_email_imap_server or 'imap.gmail.com',
        # Don't return password for security
    })


@require_POST
def save_email_settings_api(request):
    """Save email settings for tenant"""
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)
    
    try:
        data = json.loads(request.body)
        
        email_address = data.get('email_address', '').strip()
        email_password = data.get('email_password', '').strip()
        imap_server = data.get('imap_server', '').strip()
        
        if email_address:
            tenant.inbound_email_address = email_address
        
        if email_password:  # Only update if provided
            tenant.inbound_email_password = email_password
        
        if imap_server:
            tenant.inbound_email_imap_server = imap_server
        
        tenant.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Error saving email settings: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
def test_email_connection_api(request):
    """Test IMAP connection for tenant"""
    import imaplib
    
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)
    
    if not all([tenant.inbound_email_address, tenant.inbound_email_password, tenant.inbound_email_imap_server]):
        return JsonResponse({
            'success': False,
            'error': 'Email settings not configured. Please save settings first.'
        })
    
    try:
        mail = imaplib.IMAP4_SSL(tenant.inbound_email_imap_server, 993)
        mail.login(tenant.inbound_email_address, tenant.inbound_email_password)
        mail.select('INBOX')
        
        # Count unread emails
        status, messages = mail.search(None, 'UNSEEN')
        unread_count = len(messages[0].split()) if status == 'OK' and messages[0] else 0
        
        mail.logout()
        
        return JsonResponse({
            'success': True,
            'unread_count': unread_count
        })
    except imaplib.IMAP4.error as e:
        return JsonResponse({
            'success': False,
            'error': f'IMAP login failed: {str(e)}'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def order_requests(request):
    """Display order requests page"""
    return render(request, 'core/order_requests.html')


def get_order_requests_api(request):
    """Get active order requests (excludes Complete)"""
    import pytz
    
    messages = InboundMessage.objects.exclude(status='Complete').order_by('-received_at')[:100]
    pacific = pytz.timezone('America/Los_Angeles')
    
    data = []
    for m in messages:
        if m.received_at:
            local_dt = m.received_at.astimezone(pacific)
            date_str = local_dt.strftime('%m/%d/%Y')
            time_str = local_dt.strftime('%I:%M %p')
        else:
            date_str = ''
            time_str = ''
        
        data.append({
            'id': m.id,
            'source': m.source,
            'date': date_str,
            'time': time_str,
            'subject': m.subject or '',
            'sender': m.sender or '',
            'sender_name': m.sender_name or '',
            'sender_phone': m.sender_phone or '',
            'body': m.body or '',
            'transcription': m.transcription or '',
            'filename': m.filename or '',
            'duration': m.duration,
            'status': m.status or '',
            'assigned_user_id': m.assigned_user_id,
            'customer': m.customer or '',
            'notes': m.notes or '',
        })
    
    return JsonResponse({'messages': data})


def get_order_requests_complete_api(request):
    """Get completed order requests"""
    import pytz
    
    messages = InboundMessage.objects.filter(status='Complete').order_by('-received_at')[:100]
    pacific = pytz.timezone('America/Los_Angeles')
    
    data = []
    for m in messages:
        if m.received_at:
            local_dt = m.received_at.astimezone(pacific)
            date_str = local_dt.strftime('%m/%d/%Y')
            time_str = local_dt.strftime('%I:%M %p')
        else:
            date_str = ''
            time_str = ''
        
        data.append({
            'id': m.id,
            'source': m.source,
            'date': date_str,
            'time': time_str,
            'subject': m.subject or '',
            'sender': m.sender or '',
            'sender_name': m.sender_name or '',
            'sender_phone': m.sender_phone or '',
            'body': m.body or '',
            'transcription': m.transcription or '',
            'filename': m.filename or '',
            'duration': m.duration,
            'status': m.status or '',
            'assigned_user_id': m.assigned_user_id,
            'customer': m.customer or '',
            'notes': m.notes or '',
        })
    
    return JsonResponse({'messages': data})


def view_order_request_api(request, order_request_id):
    """View order request file (for voicemails/attachments)"""
    try:
        msg = InboundMessage.objects.get(id=order_request_id)
        
        if not msg.file_path or not os.path.exists(msg.file_path):
            return JsonResponse({'error': 'File not found'}, status=404)
        
        ext = os.path.splitext(msg.filename)[1].lower()
        content_types = {
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
        }
        content_type = content_types.get(ext, 'application/octet-stream')
        
        with open(msg.file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            response['Content-Disposition'] = f'inline; filename="{msg.filename}"'
            return response
            
    except InboundMessage.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@require_POST
def assign_order_request_user_api(request, order_request_id):
    """Assign user to order request"""
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        msg = InboundMessage.objects.get(id=order_request_id)
        msg.assigned_user_id = int(user_id) if user_id else None
        msg.status = 'InProgress' if user_id else 'Unassigned'
        msg.save()
        
        return JsonResponse({'success': True})
    except InboundMessage.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
def complete_order_request_api(request, order_request_id):
    """Mark order request as complete"""
    try:
        msg = InboundMessage.objects.get(id=order_request_id)
        msg.status = 'Complete'
        msg.save()
        return JsonResponse({'success': True})
    except InboundMessage.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@require_POST
def uncomplete_order_request_api(request, order_request_id):
    """Mark order request as not complete"""
    try:
        msg = InboundMessage.objects.get(id=order_request_id)
        msg.status = 'InProgress' if msg.assigned_user_id else 'Unassigned'
        msg.save()
        return JsonResponse({'success': True})
    except InboundMessage.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@require_POST
def update_order_request_notes_api(request, order_request_id):
    """Update order request notes"""
    try:
        data = json.loads(request.body)
        msg = InboundMessage.objects.get(id=order_request_id)
        msg.notes = data.get('notes', '')
        msg.save()
        return JsonResponse({'success': True})
    except InboundMessage.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@require_POST
def update_order_request_customer_api(request, order_request_id):
    """Update order request customer"""
    try:
        data = json.loads(request.body)
        msg = InboundMessage.objects.get(id=order_request_id)
        msg.customer = data.get('customer', '')
        msg.save()
        return JsonResponse({'success': True})
    except InboundMessage.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@csrf_exempt
@require_POST
def check_order_emails_api(request):
    """Check for order emails using IMAP"""
    import imaplib
    import email
    from email.header import decode_header
    from datetime import timedelta
    from django.utils import timezone
    import re
    
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)
    
    # Check if email is configured
    if not all([tenant.inbound_email_address, tenant.inbound_email_password, tenant.inbound_email_imap_server]):
        return JsonResponse({
            'success': False,
            'error': 'Email not configured. Set email address, app password, and IMAP server in admin.',
            'messages_saved': 0
        })
    
    try:
        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(tenant.inbound_email_imap_server, 993)
        mail.login(tenant.inbound_email_address, tenant.inbound_email_password)
        mail.select('INBOX')
        
        # Search for unread emails from last 5 days
        five_days_ago = (timezone.now() - timedelta(days=5)).strftime('%d-%b-%Y')
        status, messages = mail.search(None, f'(UNSEEN SINCE {five_days_ago})')
        
        if status != 'OK':
            return JsonResponse({'error': 'Failed to search emails'}, status=500)
        
        email_ids = messages[0].split()
        existing_subjects = set(InboundMessage.objects.filter(
            received_at__gte=timezone.now() - timedelta(days=5)
        ).values_list('subject', flat=True))
        
        messages_saved = 0
        
        for email_id in email_ids[-50:]:  # Process last 50 unread
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status != 'OK':
                continue
            
            msg = email.message_from_bytes(msg_data[0][1])
            
            # Decode subject
            subject, encoding = decode_header(msg['Subject'])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding or 'utf-8', errors='ignore')
            subject = subject or 'No Subject'
            
            # Skip duplicates
            if subject in existing_subjects:
                continue
            
            # Skip unwanted
            subject_lower = subject.lower()
            if 'undeliverable' in subject_lower or 'out of office' in subject_lower:
                continue
            
            # Get sender
            from_header = msg.get('From', 'Unknown')
            sender_match = re.match(r'(.+?)\s*<(.+?)>', from_header)
            if sender_match:
                sender_name = sender_match.group(1).strip().strip('"')
                sender_email = sender_match.group(2)
            else:
                sender_name = ''
                sender_email = from_header
            
            # Parse date
            date_str = msg.get('Date', '')
            try:
                from email.utils import parsedate_to_datetime
                email_date = parsedate_to_datetime(date_str)
            except:
                email_date = timezone.now()
            
            # Get body
            body = ''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        try:
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            pass
                        break
            else:
                try:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    body = str(msg.get_payload())
            
            # Clean body
            body = re.sub('<[^<]+?>', '', body).strip()[:5000]
            
            # Extract phone
            sender_phone = ''
            phone_match = re.search(r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})', body)
            if phone_match:
                sender_phone = phone_match.group(1)
            
            # Create inbound message
            InboundMessage.objects.create(
                tenant=tenant,
                source='email',
                received_at=email_date,
                subject=subject,
                sender=sender_email,
                sender_name=sender_name,
                sender_phone=sender_phone,
                body=body,
                status='Unassigned',
            )
            messages_saved += 1
            existing_subjects.add(subject)
            
            # Mark as read
            mail.store(email_id, '+FLAGS', '\\Seen')
        
        mail.logout()
        
        logger.info(f"Tenant {tenant.name}: saved {messages_saved} inbound messages")
        
        return JsonResponse({
            'success': True,
            'messages_saved': messages_saved,
            'emails_checked': len(email_ids),
            'message': f'Checked {len(email_ids)} emails, saved {messages_saved} new messages'
        })
        
    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP error: {str(e)}")
        return JsonResponse({'error': f'IMAP login failed. Check email/password. Error: {str(e)}'}, status=500)
    except Exception as e:
        logger.error(f"Email check error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)