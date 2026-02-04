"""Licenses and Vehicles API views"""
import os
import re
import json
import logging
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from ..models import License, Vehicle, User, Company, UserCompany
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


# ============================================================================
# LICENSES VIEWS
# ============================================================================

@login_required
def licenses(request):
    """Display licenses page"""
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/documents/licenses.html')


@login_required
def get_licenses_api(request):
    """Get all license records for tenant"""
    if not request.tenant:
        return JsonResponse({'error': 'No tenant'}, status=403)
    
    try:
        licenses = License.objects.filter(tenant=request.tenant).select_related('managing_user', 'company').order_by('-created_at')
        
        files = []
        for lic in licenses:
            files.append({
                'id': lic.id,
                'filename': lic.filename,
                'title': lic.title,
                'company_id': lic.company_id,
                'company_name': lic.company.companyname if lic.company else None,
                'issuance_date': lic.issuance_date.isoformat() if lic.issuance_date else None,
                'expiration_date': lic.expiration_date.isoformat() if lic.expiration_date else None,
                'managing_user_id': lic.managing_user_id,
                'managing_user_name': lic.managing_user.name if lic.managing_user else None,
                'url': f'/api/documents/licenses/{lic.filename}/view/'
            })
        
        # Get companies for dropdown
        companies = Company.objects.filter(tenant=request.tenant).values('companyid', 'companyname').order_by('companyname')
        companies_list = [{'id': c['companyid'], 'name': c['companyname']} for c in companies]
        
        # Get all users with their company associations
        users = User.objects.filter(tenant=request.tenant).values('id', 'name').order_by('name')
        users_list = [{'id': u['id'], 'name': u['name']} for u in users if u['name']]
        
        # Get user-company mappings
        user_companies = {}
        for uc in UserCompany.objects.filter(tenant=request.tenant).values('user_id', 'company_id'):
            if uc['user_id'] not in user_companies:
                user_companies[uc['user_id']] = []
            user_companies[uc['user_id']].append(uc['company_id'])
        
        return JsonResponse({
            'files': files, 
            'users': users_list, 
            'companies': companies_list,
            'user_companies': user_companies
        })
        
    except Exception as e:
        logger.error(f"Error in get_licenses_api: {str(e)}")
        return JsonResponse({'files': [], 'users': [], 'companies': [], 'user_companies': {}, 'error': str(e)})


@csrf_exempt
@login_required
def upload_license_api(request):
    """Upload a license file"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'No tenant'})
    
    try:
        file_upload = request.FILES.get('file')
        if not file_upload:
            return JsonResponse({'success': False, 'error': 'No file provided'})
        
        title = request.POST.get('title', '').strip()
        if not title:
            return JsonResponse({'success': False, 'error': 'Title is required'})
        
        # Clean filename
        original_filename = file_upload.name
        clean_filename = re.sub(r'[^a-zA-Z0-9\s._-]', '', original_filename)
        clean_filename = re.sub(r'\s+', ' ', clean_filename).strip()
        if not clean_filename or clean_filename == '.':
            clean_filename = 'file' + os.path.splitext(original_filename)[1]
        
        # Create directory
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'licenses', str(request.tenant.id))
        os.makedirs(upload_dir, exist_ok=True)
        
        # Handle filename conflicts
        filename = clean_filename
        base_name, extension = os.path.splitext(filename)
        counter = 1
        while os.path.exists(os.path.join(upload_dir, filename)):
            filename = f"{base_name}_{counter}{extension}"
            counter += 1
        
        # Save file
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, 'wb') as f:
            for chunk in file_upload.chunks():
                f.write(chunk)
        
        # Create database record
        company_id = request.POST.get('company_id') or None
        issuance_date = request.POST.get('issuance_date') or None
        expiration_date = request.POST.get('expiration_date') or None
        managing_user_id = request.POST.get('managing_user_id') or None
        
        license_obj = License.objects.create(
            tenant=request.tenant,
            filename=filename,
            title=title,
            company_id=company_id,
            issuance_date=issuance_date,
            expiration_date=expiration_date,
            managing_user_id=managing_user_id
        )
        
        return JsonResponse({'success': True, 'filename': filename, 'id': license_obj.id})
        
    except Exception as e:
        logger.error(f"Error uploading license: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
def update_license_api(request, license_id):
    """Update license metadata"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'No tenant'})
    
    try:
        data = json.loads(request.body)
        
        license_obj = License.objects.get(id=license_id, tenant=request.tenant)
        license_obj.title = data.get('title') or license_obj.title
        license_obj.company_id = data.get('company_id') or None
        license_obj.issuance_date = data.get('issuance_date') or None
        license_obj.expiration_date = data.get('expiration_date') or None
        license_obj.managing_user_id = data.get('managing_user_id') or None
        license_obj.save()
        
        return JsonResponse({'success': True})
        
    except License.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'License not found'})
    except Exception as e:
        logger.error(f"Error updating license: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def view_license_file_api(request, filename):
    """View a license file"""
    if not request.tenant:
        raise Http404("No tenant")
    
    try:
        file_path = os.path.join(settings.MEDIA_ROOT, 'licenses', str(request.tenant.id), filename)
        
        if not os.path.exists(file_path):
            raise Http404("File not found")
        
        file_ext = os.path.splitext(filename)[1].lower()
        content_type_map = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.gif': 'image/gif',
        }
        content_type = content_type_map.get(file_ext, 'application/octet-stream')
        
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            return response
            
    except Exception as e:
        raise Http404(f"Error loading file: {str(e)}")


@csrf_exempt
@login_required
def delete_license_api(request, filename):
    """Delete a license file and its record"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'No tenant'})
    
    try:
        from urllib.parse import unquote
        decoded_filename = unquote(filename)
        
        # Delete file
        file_path = os.path.join(settings.MEDIA_ROOT, 'licenses', str(request.tenant.id), decoded_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Delete database record
        License.objects.filter(tenant=request.tenant, filename=decoded_filename).delete()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================================
# VEHICLES VIEWS
# ============================================================================

@login_required
def vehicles(request):
    """Display vehicles page"""
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/documents/vehicles.html')


@login_required
def get_vehicles_api(request):
    """Get all vehicle records for tenant"""
    if not request.tenant:
        return JsonResponse({'vehicles': [], 'error': 'No tenant'})
    
    try:
        vehicles = Vehicle.objects.filter(tenant=request.tenant).order_by('-created_at')
        
        vehicles_list = []
        for v in vehicles:
            vehicles_list.append({
                'id': v.id,
                'year': v.year,
                'make': v.make,
                'model': v.model,
                'vin': v.vin,
                'license_plate': v.license_plate,
                'number': v.number,
                'driver': v.driver,
                'dmv_renewal_date': v.dmv_renewal_date.isoformat() if v.dmv_renewal_date else None,
                'company': v.company,
                'status': v.status,
                'title': v.title,
                'carb_number': v.carb_number,
                'dash_cam': v.dash_cam,
            })
        
        return JsonResponse({'vehicles': vehicles_list})
        
    except Exception as e:
        logger.error(f"Error in get_vehicles_api: {str(e)}")
        return JsonResponse({'vehicles': [], 'error': str(e)})


@csrf_exempt
@login_required
def add_vehicle_api(request):
    """Add a new vehicle"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'No tenant'})
    
    try:
        data = json.loads(request.body)
        
        vehicle = Vehicle.objects.create(
            tenant=request.tenant,
            year=data.get('year') or None,
            make=data.get('make') or '',
            model=data.get('model') or '',
            vin=data.get('vin') or '',
            license_plate=data.get('license_plate') or '',
            number=data.get('number') or '',
            driver=data.get('driver') or '',
            dmv_renewal_date=data.get('dmv_renewal_date') or None,
            company=data.get('company') or '',
            status=data.get('status') or '',
            title=data.get('title') or '',
            carb_number=data.get('carb_number') or '',
            dash_cam=data.get('dash_cam') or '',
        )
        
        return JsonResponse({'success': True, 'id': vehicle.id})
        
    except Exception as e:
        logger.error(f"Error adding vehicle: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
def update_vehicle_api(request, vehicle_id):
    """Update vehicle"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'No tenant'})
    
    try:
        data = json.loads(request.body)
        
        vehicle = Vehicle.objects.get(id=vehicle_id, tenant=request.tenant)
        vehicle.year = data.get('year') or None
        vehicle.make = data.get('make') or ''
        vehicle.model = data.get('model') or ''
        vehicle.vin = data.get('vin') or ''
        vehicle.license_plate = data.get('license_plate') or ''
        vehicle.number = data.get('number') or ''
        vehicle.driver = data.get('driver') or ''
        vehicle.dmv_renewal_date = data.get('dmv_renewal_date') or None
        vehicle.company = data.get('company') or ''
        vehicle.status = data.get('status') or ''
        vehicle.title = data.get('title') or ''
        vehicle.carb_number = data.get('carb_number') or ''
        vehicle.dash_cam = data.get('dash_cam') or ''
        vehicle.save()
        
        return JsonResponse({'success': True})
        
    except Vehicle.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vehicle not found'})
    except Exception as e:
        logger.error(f"Error updating vehicle: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
def delete_vehicle_api(request, vehicle_id):
    """Delete a vehicle"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'No tenant'})
    
    try:
        Vehicle.objects.filter(id=vehicle_id, tenant=request.tenant).delete()
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error deleting vehicle: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})
    

# =============================================================================
# VEHICLES API FUNCTIONS - Add these to core/views/licenses_vehicles.py
# =============================================================================

@login_required
def vehicles(request):
    """Display the vehicles page"""
    return render(request, 'core/documents/vehicles.html')


@login_required
def get_vehicles_api(request):
    """Get all vehicle records for tenant"""
    if not request.tenant:
        return JsonResponse({'error': 'No tenant'}, status=403)
    
    try:
        vehicles = Vehicle.objects.filter(tenant=request.tenant).order_by('-created_at')
        
        files = []
        for v in vehicles:
            files.append({
                'id': v.id,
                'year': v.year,
                'make': v.make,
                'model': v.model,
                'vin': v.vin,
                'license_plate': v.license_plate,
                'number': v.number,
                'driver': v.driver,
                'dmv_renewal_date': v.dmv_renewal_date.isoformat() if v.dmv_renewal_date else None,
                'company_id': None,
                'company_name': v.company,
                'status': v.status,
                'title': v.title,
                'carb_number': v.carb_number,
                'dash_cam': v.dash_cam,
                'created_at': v.created_at.isoformat() if v.created_at else None
            })
        
        # Get companies for dropdown
        companies = Company.objects.filter(tenant=request.tenant).order_by('companyname')
        companies_list = [{'id': c.companyid, 'name': c.companyname} for c in companies]
        
        return JsonResponse({'vehicles': files, 'companies': companies_list})
        
    except Exception as e:
        import logging
        logging.error(f"Error in get_vehicles_api: {str(e)}")
        return JsonResponse({'vehicles': [], 'companies': [], 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def add_vehicle_api(request):
    """Add a new vehicle"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'No tenant'}, status=403)
    
    try:
        import json
        data = json.loads(request.body)
        
        # Get company name if company_id provided
        company_name = None
        company_id = data.get('company_id')
        if company_id:
            try:
                company = Company.objects.get(companyid=company_id, tenant=request.tenant)
                company_name = company.companyname
            except Company.DoesNotExist:
                pass
        
        vehicle = Vehicle.objects.create(
            tenant=request.tenant,
            year=data.get('year') or None,
            make=data.get('make') or None,
            model=data.get('model') or None,
            vin=data.get('vin') or None,
            license_plate=data.get('license_plate') or None,
            number=data.get('number') or None,
            driver=data.get('driver') or None,
            dmv_renewal_date=data.get('dmv_renewal_date') or None,
            company=company_name,
            status=data.get('status') or None,
            title=data.get('title') or None,
            carb_number=data.get('carb_number') or None,
            dash_cam=data.get('dash_cam') or None
        )
        
        return JsonResponse({'success': True, 'id': vehicle.id})
        
    except Exception as e:
        import logging
        logging.error(f"Error adding vehicle: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def update_vehicle_api(request, vehicle_id):
    """Update a vehicle"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'No tenant'}, status=403)
    
    try:
        import json
        data = json.loads(request.body)
        
        vehicle = Vehicle.objects.get(id=vehicle_id, tenant=request.tenant)
        
        vehicle.year = data.get('year') or None
        vehicle.make = data.get('make') or None
        vehicle.model = data.get('model') or None
        vehicle.vin = data.get('vin') or None
        vehicle.license_plate = data.get('license_plate') or None
        vehicle.number = data.get('number') or None
        vehicle.driver = data.get('driver') or None
        vehicle.dmv_renewal_date = data.get('dmv_renewal_date') or None
        # Get company name if company_id provided
        company_id = data.get('company_id')
        if company_id:
            try:
                company = Company.objects.get(companyid=company_id, tenant=request.tenant)
                vehicle.company = company.companyname
            except Company.DoesNotExist:
                vehicle.company = None
        else:
            vehicle.company = None
        vehicle.status = data.get('status') or None
        vehicle.title = data.get('title') or None
        vehicle.carb_number = data.get('carb_number') or None
        vehicle.dash_cam = data.get('dash_cam') or None
        vehicle.save()
        
        return JsonResponse({'success': True})
        
    except Vehicle.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vehicle not found'}, status=404)
    except Exception as e:
        import logging
        logging.error(f"Error updating vehicle: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["DELETE"])
def delete_vehicle_api(request, vehicle_id):
    """Delete a vehicle"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'No tenant'}, status=403)
    
    try:
        vehicle = Vehicle.objects.get(id=vehicle_id, tenant=request.tenant)
        vehicle.delete()
        return JsonResponse({'success': True})
        
    except Vehicle.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vehicle not found'}, status=404)
    except Exception as e:
        import logging
        logging.error(f"Error deleting vehicle: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})