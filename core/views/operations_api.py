import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from core.models import (
    SOP, SOPParent, SOPChild, CompanyOperationConfig, 
    CompanyHoliday, Zone
)
from datetime import date, datetime


@require_http_methods(["POST"])
@login_required
def update_company_config(request):
    """Update company operation configuration"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        company_id = data['company_id']
        field = data['field']
        value = data['value']
        
        config, created = CompanyOperationConfig.objects.get_or_create(
            tenant=request.tenant,
            company_id=company_id
        )
        
        if field == 'operating_days':
            config.monday = value.get('monday', False)
            config.tuesday = value.get('tuesday', False)
            config.wednesday = value.get('wednesday', False)
            config.thursday = value.get('thursday', False)
            config.friday = value.get('friday', False)
            config.saturday = value.get('saturday', False)
            config.sunday = value.get('sunday', False)
        elif field == 'start_date':
            config.start_date = value
        elif field == 'monitor_user_id':
            config.monitor_user_id = int(value) if value else None
        elif field == 'verifier_user_id':
            config.verifier_user_id = int(value) if value else None
        
        config.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def toggle_holiday(request):
    """Toggle a date as holiday"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        company_id = data['company_id']
        date_str = data['date']
        
        holiday, created = CompanyHoliday.objects.get_or_create(
            tenant=request.tenant,
            company_id=company_id,
            date=date_str
        )
        
        if not created:
            holiday.delete()
            is_holiday = False
        else:
            is_holiday = True
        
        return JsonResponse({'success': True, 'is_holiday': is_holiday})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
@login_required
def get_deviations(request, parent_id):
    """Get deviations for an inspection"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        parent = SOPParent.objects.get(id=parent_id)
        children = SOPChild.objects.filter(sop_parent=parent)
        
        deviations = []
        all_items = []
        
        for child in children:
            sop = SOP.objects.filter(sop_did=child.sop_did).first()
            item = {
                'child_id': child.id,
                'sop_did': child.sop_did,
                'description': sop.description if sop else '',
                'passed': child.passed,
                'failed': child.failed,
                'notes': child.notes or '',
                'deviation_reason': child.deviation_reason or '',
                'corrective_action': child.corrective_action or ''
            }
            all_items.append(item)
            
            if child.failed and child.deviation_reason:
                deviations.append(item)
        
        return JsonResponse({
            'success': True,
            'deviations': deviations,
            'all_items': all_items
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def save_corrective_actions(request):
    """Save corrective actions for deviations"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        parent_id = data['parent_id']
        actions = data['actions']
        
        for action in actions:
            child = SOPChild.objects.get(id=action['child_id'])
            child.corrective_action = action['corrective_action']
            child.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def submit_verification(request):
    """Submit verification for an inspection"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        parent_id = data['parent_id']
        verifier_name = data['verifier_name']
        verifier_signature = data['verifier_signature']
        
        parent = SOPParent.objects.get(id=parent_id)
        parent.verified = True
        parent.verifier_name = verifier_name
        parent.verifier_signature = verifier_signature
        parent.verified_at = datetime.now()
        parent.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def save_verifier_signature(request):
    """Save verifier's saved signature"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        company_id = data['company_id']
        signature = data['signature']
        
        config, created = CompanyOperationConfig.objects.get_or_create(
            tenant=request.tenant,
            company_id=company_id
        )
        config.verifier_signature = signature
        config.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
@login_required
def get_verifier_signature(request):
    """Get verifier's saved signature"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        company_id = request.GET.get('company_id')
        config = CompanyOperationConfig.objects.filter(company_id=company_id).first()
        
        if config and config.verifier_signature:
            return JsonResponse({
                'success': True,
                'signature': config.verifier_signature,
                'has_signature': True
            })
        else:
            return JsonResponse({
                'success': True,
                'has_signature': False
            })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def save_monitor_signature(request):
    """Save monitor's saved signature"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        company_id = data['company_id']
        signature = data['signature']
        
        config, created = CompanyOperationConfig.objects.get_or_create(
            tenant=request.tenant,
            company_id=company_id
        )
        config.monitor_signature = signature
        config.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
@login_required
def get_monitor_signature(request):
    """Get monitor's saved signature"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        company_id = request.GET.get('company_id')
        config = CompanyOperationConfig.objects.filter(company_id=company_id).first()
        
        if config and config.monitor_signature:
            return JsonResponse({
                'success': True,
                'signature': config.monitor_signature,
                'has_signature': True
            })
        else:
            return JsonResponse({
                'success': True,
                'has_signature': False
            })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
@login_required
def get_operations_config(request):
    """Get operations configuration"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        company_id = request.GET.get('company_id')
        config = CompanyOperationConfig.objects.filter(company_id=company_id).first()
        
        if config:
            return JsonResponse({
                'success': True,
                'config': {
                    'start_date': config.start_date.isoformat() if config.start_date else None,
                    'monday': config.monday,
                    'tuesday': config.tuesday,
                    'wednesday': config.wednesday,
                    'thursday': config.thursday,
                    'friday': config.friday,
                    'saturday': config.saturday,
                    'sunday': config.sunday,
                    'monitor_user_id': config.monitor_user_id,
                    'verifier_user_id': config.verifier_user_id,
                }
            })
        else:
            return JsonResponse({'success': True, 'config': None})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
@login_required
def get_sop_list(request):
    """Get SOP list for a company"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        company_id = request.GET.get('company_id')
        sops = SOP.objects.filter(company_id=company_id).select_related('zone').order_by('sop_did')
        
        sop_list = []
        for sop in sops:
            sop_list.append({
                'sop_did': sop.sop_did,
                'description': sop.description,
                'zone_name': sop.zone.name if sop.zone else '',
                'zone_id': sop.zone_id,
                'pre': sop.pre,
                'mid': sop.mid,
                'post': sop.post,
                'input_required': sop.input_required,
                'image_required': sop.image_required,
            })
        
        return JsonResponse({'success': True, 'sops': sop_list})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def create_sop(request):
    """Create a new SOP"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        
        zone = Zone.objects.get(id=data['zone_id'])
        
        # Get next SOP ID
        max_id = SOP.objects.aggregate(Max('sop_did'))['sop_did__max'] or 0
        new_id = max_id + 1
        
        sop = SOP.objects.create(
            tenant=request.tenant,
            sop_did=new_id,
            description=data['description'],
            zone=zone,
            company_id=data['company_id'],
            pre=data.get('pre', False),
            mid=data.get('mid', False),
            post=data.get('post', False),
            input_required=data.get('input_required', False),
            image_required=data.get('image_required', False),
        )
        
        return JsonResponse({'success': True, 'sop_id': sop.sop_did})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def update_sop(request):
    """Update an SOP"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        sop = SOP.objects.get(sop_did=data['sop_did'])
        
        field = data['field']
        value = data['value']
        
        if field in ['pre', 'mid', 'post', 'input_required', 'image_required']:
            setattr(sop, field, value)
        elif field in ['description']:
            setattr(sop, field, value)
        elif field == 'zone_id':
            sop.zone_id = value
        
        sop.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def delete_sop(request):
    """Delete an SOP"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        sop = SOP.objects.get(sop_did=data['sop_did'])
        sop.delete()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
@login_required
def get_zones(request):
    """Get zones for a company"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        company_id = request.GET.get('company_id')
        zones = Zone.objects.filter(company_id=company_id).order_by('name')
        
        zone_list = []
        for zone in zones:
            sop_count = SOP.objects.filter(zone=zone).count()
            zone_list.append({
                'id': zone.id,
                'name': zone.name,
                'sop_count': sop_count
            })
        
        return JsonResponse({'success': True, 'zones': zone_list})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def create_zone(request):
    """Create a new zone"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        
        zone = Zone.objects.create(
            tenant=request.tenant,
            name=data['zone_name'],
            company_id=data['company_id']
        )
        
        return JsonResponse({'success': True, 'zone_id': zone.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
@login_required
def delete_zone(request):
    """Delete a zone"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        zone = Zone.objects.get(id=data['zone_id'])
        
        # Check if any SOPs use this zone
        sop_count = SOP.objects.filter(zone=zone).count()
        if sop_count > 0:
            return JsonResponse({
                'success': False,
                'error': f'Cannot delete zone. {sop_count} SOPs are using it.'
            })
        
        zone.delete()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
@login_required
def get_calendar_data(request):
    """Get calendar data for bulk reports"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        company_id = request.GET.get('company_id')
        
        config = CompanyOperationConfig.objects.filter(company_id=company_id).first()
        if not config:
            return JsonResponse({'success': True, 'calendar_data': {}})
        
        parents = SOPParent.objects.filter(company_id=company_id)
        
        holidays = CompanyHoliday.objects.filter(company_id=company_id)
        holiday_dates = [h.date.isoformat() for h in holidays]
        
        calendar_data = {}
        for parent in parents:
            date_str = parent.date.isoformat()
            
            if date_str not in calendar_data:
                weekday = parent.date.weekday()
                is_operating_day = config.is_operating_day(weekday) and date_str not in holiday_dates
                
                calendar_data[date_str] = {
                    'preop': None,
                    'midday': None,
                    'postop': None,
                    'preop_verified': False,
                    'midday_verified': False,
                    'postop_verified': False,
                    'is_operating_day': is_operating_day
                }
            
            if parent.shift == 'Pre-Op':
                calendar_data[date_str]['preop'] = parent.completed
                calendar_data[date_str]['preop_verified'] = parent.verified
            elif parent.shift == 'Mid-Day':
                calendar_data[date_str]['midday'] = parent.completed
                calendar_data[date_str]['midday_verified'] = parent.verified
            elif parent.shift == 'Post-Op':
                calendar_data[date_str]['postop'] = parent.completed
                calendar_data[date_str]['postop_verified'] = parent.verified
        
        return JsonResponse({'success': True, 'calendar_data': calendar_data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["GET"])
@login_required
def get_inspection_images(request, parent_id):
    """Get images from an inspection"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        parent = SOPParent.objects.get(id=parent_id)
        children = SOPChild.objects.filter(sop_parent=parent).exclude(image='')
        
        images = []
        for child in children:
            sop = SOP.objects.filter(sop_did=child.sop_did).first()
            images.append({
                'sop_did': child.sop_did,
                'description': sop.description if sop else '',
                'passed': child.passed,
                'failed': child.failed,
                'notes': child.notes or '',
                'deviation_reason': child.deviation_reason or '',
                'image': child.image
            })
        
        return JsonResponse({'success': True, 'images': images})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})