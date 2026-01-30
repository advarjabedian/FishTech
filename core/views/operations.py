from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.contrib.auth.models import User
from core.models import (
    SOP, SOPParent, SOPChild, Company, CompanyOperationConfig, 
    CompanyHoliday, Zone, TenantUser, set_current_tenant
)
from datetime import datetime, timedelta, date
import json
import logging

logger = logging.getLogger(__name__)


def ensure_tenant(view_func):
    """Decorator to set tenant for TenantManager"""
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.tenant:
            set_current_tenant(request.tenant)
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@ensure_tenant
def operations_dashboard(request):
    """Main operations dashboard view"""
    if not request.tenant:
        return redirect('login')
    
    companies = Company.objects.all().order_by('companyname')
    
    selected_date = request.GET.get('date', datetime.now().strftime('%Y-%m-%d'))
    selected_company_id = request.GET.get('company_id')
    
    selected_company = None
    if not selected_company_id and companies.exists():
        selected_company_id = companies.first().companyid
        selected_company = companies.first()
    elif selected_company_id:
        selected_company = companies.filter(companyid=selected_company_id).first()
    
    # Get SOPs for the selected company, filtered by date (only SOPs that existed on selected date)
    sops = SOP.objects.filter(company_id=selected_company_id).filter(
        Q(created_at__isnull=True) | Q(created_at__lte=selected_date)
    ).order_by('sop_did') if selected_company_id else []
    
    pre_op_count = sops.filter(pre=True).count() if sops else 0
    mid_day_count = sops.filter(mid=True).count() if sops else 0
    post_op_count = sops.filter(post=True).count() if sops else 0
    
    # Get existing inspections for this date
    existing_inspections = SOPParent.objects.filter(
        company_id=selected_company_id,
        date=selected_date
    ).prefetch_related('children') if selected_company_id else []
    
    preop_data = None
    midday_data = None
    postop_data = None
    
    for parent in existing_inspections:
        inspector = User.objects.filter(id=parent.user_inspected_id).first()
        inspector_name = f"{inspector.first_name} {inspector.last_name}" if inspector else "Unknown"
        
        # Get valid SOP IDs for this shift (filtered by date)
        if parent.shift == 'Pre-Op':
            valid_sop_ids = list(SOP.objects.filter(company_id=selected_company_id, pre=True).filter(
                Q(created_at__isnull=True) | Q(created_at__lte=parent.date)
            ).values_list('sop_did', flat=True))
        elif parent.shift == 'Mid-Day':
            valid_sop_ids = list(SOP.objects.filter(company_id=selected_company_id, mid=True).filter(
                Q(created_at__isnull=True) | Q(created_at__lte=parent.date)
            ).values_list('sop_did', flat=True))
        else:
            valid_sop_ids = list(SOP.objects.filter(company_id=selected_company_id, post=True).filter(
                Q(created_at__isnull=True) | Q(created_at__lte=parent.date)
            ).values_list('sop_did', flat=True))
        
        items_completed = parent.children.filter(
            Q(passed=True) | Q(failed=True),
            sop_did__in=valid_sop_ids
        ).count()
        
        shift_data = {
            'parent_id': parent.id,
            'time': parent.time.strftime('%I:%M %p'),
            'deviations': parent.children.filter(failed=True).count(),
            'inspected_name': inspector_name,
            'completed': parent.completed,
            'items_completed': items_completed,
            'items_total': len(valid_sop_ids),
            'verified': parent.verified,
            'verifier_name': parent.verifier_name,
        }
        
        if parent.shift == 'Pre-Op':
            preop_data = shift_data
        elif parent.shift == 'Mid-Day':
            midday_data = shift_data
        else:
            postop_data = shift_data
   

    # Get users for current tenant only
    tenant_users = TenantUser.objects.filter(
        tenant=request.tenant
    ).select_related('user').order_by('user__first_name', 'user__last_name')

    users = [{'userid': tu.user.id, 'name': tu.user.get_full_name() or tu.user.username} for tu in tenant_users]
    
    # Get incomplete/unverified counts
    incomplete_count = 0
    unverified_count = 0
    monitor_name = None
    verifier_name = None
    verifier_user_id = None
    
    if selected_company_id:
        config = CompanyOperationConfig.objects.filter(company_id=selected_company_id).first()
        
        if config:
            start_date = config.start_date or date(2025, 1, 1)
            
            if config.monitor_user_id:
                monitor = User.objects.filter(id=config.monitor_user_id).first()
                monitor_name = f"{monitor.first_name} {monitor.last_name}" if monitor else None
            
            if config.verifier_user_id:
                verifier = User.objects.filter(id=config.verifier_user_id).first()
                verifier_name = f"{verifier.first_name} {verifier.last_name}" if verifier else None
                verifier_user_id = config.verifier_user_id
            
            # Count incomplete and unverified
            today = date.today()
            parents = SOPParent.objects.filter(
                company_id=selected_company_id,
                date__gte=start_date,
                date__lt=today
            ).values('date', 'shift', 'completed', 'verified')
            
            lookup = {}
            for p in parents:
                key = (p['date'], p['shift'])
                lookup[key] = {'completed': p['completed'], 'verified': p['verified']}
            
            holidays = set(CompanyHoliday.objects.filter(
                company_id=selected_company_id
            ).values_list('date', flat=True))
            
            current = start_date
            while current < today:
                if config.is_operating_day(current.weekday()) and current not in holidays:
                    preop = lookup.get((current, 'Pre-Op'), {})
                    midday = lookup.get((current, 'Mid-Day'), {})
                    postop = lookup.get((current, 'Post-Op'), {})
                    
                    if not (preop.get('completed') and midday.get('completed') and postop.get('completed')):
                        incomplete_count += 1
                    
                    for shift_data in [preop, midday, postop]:
                        if shift_data.get('completed') and not shift_data.get('verified'):
                            unverified_count += 1
                
                current += timedelta(days=1)
    
    is_holiday = CompanyHoliday.objects.filter(
        company_id=selected_company_id,
        date=selected_date
    ).exists() if selected_company_id else False
    
    context = {
        'companies': companies,
        'selected_company': selected_company,
        'selected_company_id': int(selected_company_id) if selected_company_id else None,
        'selected_date': selected_date,
        'pre_op_count': pre_op_count,
        'mid_day_count': mid_day_count,
        'post_op_count': post_op_count,
        'preop_data': preop_data,
        'midday_data': midday_data,
        'postop_data': postop_data,
        'users': users,
        'current_user_id': request.user.id,
        'incomplete_count': incomplete_count,
        'unverified_count': unverified_count,
        'monitor_name': monitor_name,
        'verifier_name': verifier_name,
        'is_holiday': is_holiday,
        'verifier_user_id': verifier_user_id,
    }
    
    return render(request, 'core/DailyInspections/operations.html', context)


@login_required
@ensure_tenant
def inspection_form(request, parent_id):
    """Inspection form view"""
    if not request.tenant:
        return redirect('login')
    
    sop_parent = get_object_or_404(SOPParent, id=parent_id)
    
    # Get SOPs for this company and shift (only SOPs that existed on inspection date)
    if sop_parent.shift == 'Pre-Op':
        sops = SOP.objects.filter(company_id=sop_parent.company_id, pre=True).filter(
            Q(created_at__isnull=True) | Q(created_at__lte=sop_parent.date)
        ).order_by('zone__name', 'sop_did')
    elif sop_parent.shift == 'Mid-Day':
        sops = SOP.objects.filter(company_id=sop_parent.company_id, mid=True).filter(
            Q(created_at__isnull=True) | Q(created_at__lte=sop_parent.date)
        ).order_by('zone__name', 'sop_did')
    else:
        sops = SOP.objects.filter(company_id=sop_parent.company_id, post=True).filter(
            Q(created_at__isnull=True) | Q(created_at__lte=sop_parent.date)
        ).order_by('zone__name', 'sop_did')
    
    # Get existing child records
    existing_children = {child.sop_did: child for child in sop_parent.children.all()}
    
    # Build SOPs list with existing data
    sop_list = []
    for sop in sops:
        child = existing_children.get(sop.sop_did)
        sop_list.append({
            'SopDId': sop.sop_did,
            'Description': sop.description,
            'Zones_Zone': sop.zone.name if sop.zone else '',
            'Input': sop.input_required,
            'ImageRequired': sop.image_required,
            'existing_passed': child.passed if child else False,
            'existing_failed': child.failed if child else False,
            'existing_notes': child.notes if child else '',
            'existing_deviation_reason': child.deviation_reason if child else '',
            'existing_image': child.image if child else '',
        })
    
    # Get users for current tenant only
    tenant_users = TenantUser.objects.filter(
        tenant=request.tenant
    ).select_related('user').order_by('user__first_name', 'user__last_name')

    users = [{'userid': tu.user.id, 'name': tu.user.get_full_name() or tu.user.username} for tu in tenant_users]
    
    # Check if current user is the monitor
    config = CompanyOperationConfig.objects.filter(company_id=sop_parent.company_id).first()
    is_monitor = config and config.monitor_user_id == request.user.id
    
    context = {
        'sop_parent': sop_parent,
        'sops': sop_list,
        'users': users,
        'company_name': sop_parent.company.companyname,
        'current_user_name': f"{request.user.first_name} {request.user.last_name}",
        'is_monitor': is_monitor,
    }
    
    return render(request, 'core/DailyInspections/inspection_form.html', context)



@login_required
@ensure_tenant
def operations_admin(request):
    """Admin view for operations"""
    if not request.tenant:
        return redirect('login')
    
    # Set tenant for TenantManager filtering
    from core.models import set_current_tenant
    set_current_tenant(request.tenant)
    
    companies = Company.objects.all().order_by('companyname')
    
    # Get users for dropdowns
    tenant_users = TenantUser.objects.filter(
        tenant=request.tenant
    ).select_related('user').order_by('user__first_name', 'user__last_name')
    users = [{'id': tu.user.id, 'name': tu.user.get_full_name() or tu.user.username} for tu in tenant_users]
    
    selected_company_id = request.GET.get('company_id')
    filter_type = request.GET.get('filter', 'incomplete')
    
    if selected_company_id:
        # Drilldown view
        company = get_object_or_404(Company, companyid=selected_company_id)
        config = CompanyOperationConfig.objects.filter(company=company).first()
        
        start_date = config.start_date if config else date(2025, 1, 1)
        today = date.today()
        
        parents = SOPParent.objects.filter(
            company=company,
            date__gte=start_date,
            date__lt=today
        ).values('date', 'shift', 'completed', 'verified')
        
        lookup = {}
        for p in parents:
            key = p['date']
            if key not in lookup:
                lookup[key] = {}
            lookup[key][p['shift']] = {'completed': p['completed'], 'verified': p['verified']}
        
        holidays = set(CompanyHoliday.objects.filter(company=company).values_list('date', flat=True))
        
        incomplete_days = []
        current = start_date
        
        while current < today:
            if config and config.is_operating_day(current.weekday()) and current not in holidays:
                day_data = lookup.get(current, {})
                preop = day_data.get('Pre-Op', {})
                midday = day_data.get('Mid-Day', {})
                postop = day_data.get('Post-Op', {})
                
                incomplete_days.append({
                    'date': current,
                    'preop_complete': preop.get('completed', False),
                    'preop_verified': preop.get('verified', False),
                    'midday_complete': midday.get('completed', False),
                    'midday_verified': midday.get('verified', False),
                    'postop_complete': postop.get('completed', False),
                    'postop_verified': postop.get('verified', False),
                })
            
            current += timedelta(days=1)
        
        context = {
            'selected_company': company,
            'config': config,
            'incomplete_days': incomplete_days,
            'users': users,
        }
    else:
        # Summary view
        company_stats = []
        
        for company in companies:
            config = CompanyOperationConfig.objects.filter(company=company).first()
            start_date = config.start_date if config else date(2025, 1, 1)
            today = date.today()
            
            parents = SOPParent.objects.filter(
                company=company,
                date__gte=start_date,
                date__lt=today
            ).values('date', 'shift', 'completed', 'verified')
            
            lookup = {}
            for p in parents:
                key = (p['date'], p['shift'])
                lookup[key] = {'completed': p['completed'], 'verified': p['verified']}
            
            holidays = set(CompanyHoliday.objects.filter(company=company).values_list('date', flat=True))
            
            incomplete_count = 0
            unverified_count = 0
            current = start_date
            
            while current < today:
                if config and config.is_operating_day(current.weekday()) and current not in holidays:
                    preop = lookup.get((current, 'Pre-Op'), {})
                    midday = lookup.get((current, 'Mid-Day'), {})
                    postop = lookup.get((current, 'Post-Op'), {})
                    
                    if not (preop.get('completed') and midday.get('completed') and postop.get('completed')):
                        incomplete_count += 1
                    
                    for shift_data in [preop, midday, postop]:
                        if shift_data.get('completed') and not shift_data.get('verified'):
                            unverified_count += 1
                
                current += timedelta(days=1)
            
            # Ensure config exists
            if not config:
                config = CompanyOperationConfig.objects.create(
                    tenant=request.tenant,
                    company=company
                )
            
            company_stats.append({
                'id': company.companyid,
                'name': company.companyname,
                'incomplete_count': incomplete_count,
                'unverified_count': unverified_count,
                'config': config,
            })
        
        # Calculate totals
        total_incomplete = sum(c['incomplete_count'] for c in company_stats)
        total_unverified = sum(c['unverified_count'] for c in company_stats)
        
        context = {
            'company_stats': company_stats,
            'users': users,
            'total_incomplete': total_incomplete,
            'total_unverified': total_unverified,
        }
    
    return render(request, 'core/DailyInspections/operations_admin.html', context)


@login_required
@ensure_tenant
def print_sop_schedule(request):
    """Print SOP schedule"""
    if not request.tenant:
        return redirect('login')
    
    company_id = request.GET.get('company_id')
    company = get_object_or_404(Company, companyid=company_id)
    
    sops = SOP.objects.filter(company=company).select_related('zone').order_by('zone__name', 'sop_did')
    
    context = {
        'company': company,
        'sops': sops,
    }
    
    return render(request, 'core/DailyInspections/print_sop_schedule.html', context)


# API ENDPOINTS

@require_POST
@login_required
@ensure_tenant
def start_inspection(request):
    """Create a new inspection parent record"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        shift = data['shift']
        company_id = data['company_id']
        date_str = data['date']
        user_id = data['user_id']
        
        # Check if already exists
        existing = SOPParent.objects.filter(
            company_id=company_id,
            date=date_str,
            shift=shift
        ).first()
        
        if existing:
            parent_id = existing.id
        else:
            parent = SOPParent.objects.create(
                tenant=request.tenant,
                company_id=company_id,
                date=date_str,
                time=datetime.now().time(),
                shift=shift,
                user_inspected_id=user_id,
                completed=False,
                verified=False,
            )
            parent_id = parent.id
        
        return JsonResponse({
            'success': True,
            'redirect_url': f'/operations/inspection/{parent_id}/'
        })
    except Exception as e:
        logger.error(f"Error starting inspection: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
@login_required
@ensure_tenant
def save_inspection(request, parent_id):
    """Save inspection data"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        parent = get_object_or_404(SOPParent, id=parent_id)
        
        # Handle toggle complete
        if 'toggle_complete' in data:
            parent.completed = data['toggle_complete']
            
            if data['toggle_complete'] and 'inspector_name' in data:
                parent.inspector_name = data['inspector_name']
                parent.inspector_signature = data['inspector_signature']
                parent.completed_at = datetime.now()
            
            parent.save()
            return JsonResponse({'success': True, 'completed': parent.completed})
        
        # Handle saving items
        items = data.get('items', [])
        
        for item in items:
            child, created = SOPChild.objects.get_or_create(
                sop_parent=parent,
                sop_did=item['sop_did']
            )
            
            child.passed = item.get('passed', False)
            child.failed = item.get('failed', False)
            child.notes = item.get('notes', '')
            child.deviation_reason = item.get('deviation_reason', '')
            child.image = item.get('image', '')
            child.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Error saving inspection: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
@login_required
@ensure_tenant
def update_inspection_time(request, parent_id):
    """Update inspection time"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        parent = get_object_or_404(SOPParent, id=parent_id)
        parent.time = data['time']
        parent.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
@login_required
@ensure_tenant
def update_inspection_inspector(request, parent_id):
    """Update inspection inspector"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        parent = get_object_or_404(SOPParent, id=parent_id)
        parent.user_inspected_id = data['user_id']
        parent.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    

@login_required
@ensure_tenant
def generate_operational_report(request, parent_id):
    """Generate operational report PDF - placeholder"""
    if not request.tenant:
        return redirect('login')
    # TODO: Implement PDF generation
    from django.http import HttpResponse
    return HttpResponse("Operational report generation not yet implemented", status=501)


@login_required
@ensure_tenant
def generate_deviations_report(request, parent_id):
    """Generate deviations report PDF - placeholder"""
    if not request.tenant:
        return redirect('login')
    # TODO: Implement PDF generation
    from django.http import HttpResponse
    return HttpResponse("Deviations report generation not yet implemented", status=501)


@login_required
@ensure_tenant
def generate_bulk_report(request):
    """Generate bulk reports PDF - placeholder"""
    if not request.tenant:
        return redirect('login')
    # TODO: Implement PDF generation
    from django.http import HttpResponse
    return HttpResponse("Bulk report generation not yet implemented", status=501)