from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from core.models import (
    Company, HACCPDocument, HACCPProductType, CompanyProductType,
    CompanyHACCPOwner, CompanyCertificate
)
from django.contrib.auth.models import User
from django.db.models import Count, Q
import json
from datetime import datetime


@login_required
def haccp(request):
    """HACCP main page showing all companies"""
    if not request.tenant:
        return redirect('admin:index')
    
    companies = list(Company.objects.filter(
        companyname__in=['FRS', 'GSS', 'NCF', 'PFF', 'CPI', 'USG']
    ).order_by('companyname'))
    
    users = User.objects.all().order_by('username')
    
    # Get owner mappings
    owner_mappings = {owner.company_id: owner.user_id for owner in CompanyHACCPOwner.objects.all()}
    
    # Add owner_id to each company object
    for company in companies:
        company.owner_id = owner_mappings.get(company.companyid)
    
    return render(request, 'core/haccp/haccp.html', {
        'companies': companies,
        'users': users
    })


@login_required
def haccp_company(request, company_id):
    """HACCP company/product type grid"""
    if not request.tenant:
        return redirect('admin:index')
    
    # Handle master set (company_id = 0)
    if company_id == 0:
        company = type('obj', (object,), {
            'companyid': 0,
            'companyname': 'Master Set'
        })()
        
        # Get all active product types across all companies
        active_types = CompanyProductType.objects.filter(
            is_active=True
        ).values_list('product_type', flat=True).distinct()
    else:
        company = get_object_or_404(Company, companyid=company_id)
        
        # Get active product types for this company
        active_types = CompanyProductType.objects.filter(
            company_id=company_id,
            is_active=True
        ).values_list('product_type', flat=True)
    
    product_type_map = {
        'box-in-box-out': 'Box In - Box Out',
        'live-molluscan': 'Live Molluscan',
        'non-scombroid': 'Non-Scombroid',
        'scombroid-haccp': 'Scombroid HACCP',
        'smoked-fish': 'Smoked Fish'
    }
    
    product_types = [product_type_map[pt] for pt in active_types if pt in product_type_map]
    
    return render(request, 'core/haccp/haccp_company.html', {
        'company': company,
        'product_types': product_types
    })


@login_required
def haccp_documents(request, company_id, product_type):
    """HACCP documents for specific company/product type"""
    if not request.tenant:
        return redirect('admin:index')
    
    # Handle master set (company_id = 0)
    if company_id == 0:
        company = type('obj', (object,), {
            'companyid': 0,
            'companyname': 'Master Set'
        })()
    else:
        company = get_object_or_404(Company, companyid=company_id)
    
    current_year = datetime.now().year
    
    # Convert slug back to readable name
    product_type_map = {
        'box-in-box-out': 'Box In - Box Out',
        'live-molluscan': 'Live Molluscan',
        'non-scombroid': 'Non-Scombroid',
        'scombroid-haccp': 'Scombroid HACCP',
        'smoked-fish': 'Smoked Fish'
    }
    
    product_type_name = product_type_map.get(product_type, product_type)
    
    document_types = [
        {
            'name': 'Product Description',
            'icon': 'bi-file-earmark-text',
            'type': 'product_description'
        },
        {
            'name': 'Flow Chart',
            'icon': 'bi-diagram-3',
            'type': 'flow_chart'
        },
        {
            'name': 'Hazard Analysis',
            'icon': 'bi-exclamation-triangle',
            'type': 'hazard_analysis'
        },
        {
            'name': 'CCP Summary',
            'icon': 'bi-list-check',
            'type': 'ccp_summary'
        }
    ]
    
    # Find the active set (latest completed version where all 4 docs are completed)
    version_stats = HACCPDocument.objects.filter(
        company_id=company_id if company_id != 0 else None,
        product_type=product_type,
        year=current_year
    ).values('version').annotate(
        total_docs=Count('id'),
        completed_docs=Count('id', filter=Q(status='completed'))
    ).filter(total_docs=4, completed_docs=4).order_by('-version')
    
    active_version = version_stats.first()['version'] if version_stats.exists() else None
    
    # Check if viewing a specific version from query params
    year_param = request.GET.get('year')
    version_param = request.GET.get('version')
    
    if year_param and version_param:
        current_version = int(version_param)
        year_to_display = int(year_param)
    else:
        if company_id == 0:
            # Get the current working version (highest version number)
            current_version = HACCPDocument.objects.filter(
                company_id=None,
                product_type=product_type,
                year=current_year
            ).order_by('-version').values_list('version', flat=True).first()
        else:
            # Get the latest COMPLETED set only
            completed_sets = HACCPDocument.objects.filter(
                company_id=company_id,
                product_type=product_type,
                year=current_year
            ).values('version').annotate(
                total_docs=Count('id'),
                completed_docs=Count('id', filter=Q(status='completed'))
            ).filter(total_docs=4, completed_docs=4).order_by('-version')
            
            if completed_sets.exists():
                current_version = completed_sets.first()['version']
            else:
                current_version = None
        
        if current_version is None:
            current_version = 0
        
        year_to_display = current_year
    
    # Check if there's ANY in-progress set for current year
    all_versions_check = HACCPDocument.objects.filter(
        company_id=company_id if company_id != 0 else None,
        product_type=product_type,
        year=current_year
    ).values('version').annotate(
        total_docs=Count('id'),
        completed_docs=Count('id', filter=Q(status='completed'))
    )
    
    has_in_progress_set = False
    for version_check in all_versions_check:
        if version_check['total_docs'] < 4 or version_check['completed_docs'] < 4:
            has_in_progress_set = True
            break
    
    # Get documents for current version
    documents = []
    completed_count = 0
    
    for doc_type in document_types:
        doc = HACCPDocument.objects.filter(
            company_id=company_id if company_id != 0 else None,
            product_type=product_type,
            document_type=doc_type['type'],
            year=year_to_display,
            version=current_version
        ).first() if current_version else None
        
        if doc:
            documents.append({
                'name': doc_type['name'],
                'icon': doc_type['icon'],
                'type': doc_type['type'],
                'status': doc.status,
                'status_display': doc.get_status_display(),
                'approved_date': doc.approved_date,
                'approved_by': doc.approved_by
            })
            if doc.status == 'completed':
                completed_count += 1
        else:
            documents.append({
                'name': doc_type['name'],
                'icon': doc_type['icon'],
                'type': doc_type['type'],
                'status': 'not_started',
                'status_display': 'Not Started',
                'approved_date': None,
                'approved_by': None
            })
    
    total_documents = len(document_types)
    set_is_complete = (completed_count == total_documents)
    completion_percentage = int((completed_count / total_documents) * 100)
    
    # For company views, check if there's any completed set for current year
    has_completed_set = False
    if company_id != 0:
        completed_sets = HACCPDocument.objects.filter(
            company_id=company_id,
            product_type=product_type,
            year=year_to_display
        ).values('version').annotate(
            total_docs=Count('id'),
            completed_docs=Count('id', filter=Q(status='completed'))
        ).filter(total_docs=4, completed_docs=4)
        
        has_completed_set = completed_sets.exists()
    
    return render(request, 'core/haccp/haccp_documents.html', {
        'company': company,
        'product_type': product_type_name,
        'product_type_slug': product_type,
        'documents': documents,
        'completed_count': completed_count,
        'total_documents': total_documents,
        'set_is_complete': set_is_complete,
        'completion_percentage': completion_percentage,
        'current_year': year_to_display,
        'current_version': current_version,
        'active_version': active_version,
        'has_in_progress_set': has_in_progress_set,
        'has_completed_set': has_completed_set
    })


@login_required
def haccp_document_view(request, company_id, product_type, document_type):
    """View/edit specific HACCP document"""
    if not request.tenant:
        return redirect('admin:index')
    
    # Handle master set (company_id = 0)
    if company_id == 0:
        company = type('obj', (object,), {
            'companyid': 0,
            'companyname': 'Master Set'
        })()
    else:
        company = get_object_or_404(Company, companyid=company_id)
    
    # Check if viewing a specific year/version
    year_param = request.GET.get('year')
    version_param = request.GET.get('version')
    
    if year_param and version_param:
        document = HACCPDocument.objects.filter(
            company_id=company_id if company_id != 0 else None,
            product_type=product_type,
            document_type=document_type,
            year=int(year_param),
            version=int(version_param)
        ).first()
        
        if not document:
            document = HACCPDocument.objects.create(
                tenant=request.tenant,
                company_id=company_id if company_id != 0 else None,
                product_type=product_type,
                document_type=document_type,
                year=int(year_param),
                version=int(version_param),
                status='not_started',
                document_data={}
            )
        
        latest_version = HACCPDocument.objects.filter(
            company_id=company_id if company_id != 0 else None,
            product_type=product_type,
            document_type=document_type,
            year=int(year_param)
        ).order_by('-version').first()
        
        is_viewing_old_version = (latest_version and latest_version.version != document.version)
    else:
        current_year = datetime.now().year
        year = request.GET.get('year', current_year)
        
        last_completed = HACCPDocument.objects.filter(
            company_id=company_id if company_id != 0 else None,
            product_type=product_type,
            document_type=document_type,
            year=year,
            status='completed'
        ).order_by('-version').first()
        
        in_progress = HACCPDocument.objects.filter(
            company_id=company_id if company_id != 0 else None,
            product_type=product_type,
            document_type=document_type,
            year=year,
            status__in=['not_started', 'in_progress']
        ).order_by('-version').first()
        
        if in_progress:
            document = in_progress
            is_viewing_old_version = False
        elif last_completed:
            document = last_completed
            is_viewing_old_version = False
        else:
            document = HACCPDocument.objects.create(
                tenant=request.tenant,
                company_id=company_id if company_id != 0 else None,
                product_type=product_type,
                document_type=document_type,
                year=year,
                version=1,
                status='not_started',
                document_data={}
            )
            is_viewing_old_version = False
    
    is_read_only = (company_id != 0) or is_viewing_old_version or document.status == 'completed'
    
    product_type_map = {
        'box-in-box-out': 'Box In - Box Out',
        'live-molluscan': 'Live Molluscan',
        'non-scombroid': 'Non-Scombroid',
        'scombroid-haccp': 'Scombroid HACCP',
        'smoked-fish': 'Smoked Fish'
    }
    
    document_type_map = {
        'product_description': 'Product Description',
        'flow_chart': 'Flow Chart',
        'hazard_analysis': 'Hazard Analysis',
        'ccp_summary': 'CCP Summary'
    }
    
    product_type_name = product_type_map.get(product_type, product_type)
    document_type_name = document_type_map.get(document_type, document_type)
    
    document_data_json = json.dumps(document.document_data)
    
    return render(request, 'core/haccp/haccp_document_view.html', {
        'company': company,
        'product_type': product_type_name,
        'product_type_slug': product_type,
        'document_type': document_type_name,
        'document_type_slug': document_type,
        'document': document,
        'document_data_json': document_data_json,
        'is_viewing_old_version': is_viewing_old_version,
        'is_read_only': is_read_only
    })


@require_http_methods(["POST"])
def haccp_save_document(request, company_id, product_type, document_type):
    """Save HACCP document"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        year = int(data.get('year', datetime.now().year))
        new_version = int(data.get('version', 1))
        new_status = data.get('status', 'in_progress')
        
        existing_doc = HACCPDocument.objects.filter(
            company_id=company_id if company_id != 0 else None,
            product_type=product_type,
            document_type=document_type,
            year=year,
            version=new_version
        ).first()
        
        if existing_doc:
            document = existing_doc
        else:
            document = HACCPDocument.objects.create(
                tenant=request.tenant,
                company_id=company_id if company_id != 0 else None,
                product_type=product_type,
                document_type=document_type,
                year=year,
                version=new_version
            )
        
        document.status = new_status
        document.originated_date = data.get('originated_date') or None
        document.approved_date = data.get('approved_date') or None
        document.originated_by = data.get('originated_by', '')
        document.approved_by = data.get('approved_by', '')
        document.approved_signature = data.get('approved_signature', '')
        document.document_data = data.get('document_data', {})
        document.save()
        
        if new_status == 'completed':
            HACCPDocument.objects.filter(
                company_id=company_id if company_id != 0 else None,
                product_type=product_type,
                document_type=document_type,
                year=year,
                status__in=['not_started', 'in_progress']
            ).exclude(id=document.id).delete()
        
        return JsonResponse({'success': True, 'version': document.version})
        
    except Exception as e:
        import traceback
        return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})


def get_company_product_types(request, company_id):
    """Get active product types for a company"""
    current_year = datetime.now().year
    
    active_types = list(CompanyProductType.objects.filter(
        company_id=company_id,
        is_active=True
    ).values_list('product_type', flat=True))
    
    completed_types = []
    for product_type in active_types:
        completed_sets = HACCPDocument.objects.filter(
            company_id=company_id,
            product_type=product_type,
            year=current_year
        ).values('version').annotate(
            total_docs=Count('id'),
            completed_docs=Count('id', filter=Q(status='completed'))
        ).filter(total_docs=4, completed_docs=4)
        
        if completed_sets.exists():
            completed_types.append(product_type)
    
    return JsonResponse({
        'success': True,
        'active_types': active_types,
        'completed_types': completed_types
    })


@require_http_methods(["POST"])
def toggle_company_product_type(request, company_id):
    """Toggle a product type on/off for a company"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        product_type = data.get('product_type')
        is_active = data.get('is_active', True)
        
        company = get_object_or_404(Company, companyid=company_id)
        
        obj, created = CompanyProductType.objects.update_or_create(
            company=company,
            product_type=product_type,
            defaults={'is_active': is_active}
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
def generate_new_version(request, company_id, product_type, document_type):
    """Generate a new set version (all 4 documents) based on the last completed set"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        current_year = datetime.now().year
        
        existing_version = HACCPDocument.objects.filter(
            company_id=company_id if company_id != 0 else None,
            product_type=product_type,
            year=current_year
        ).order_by('-version').values_list('version', flat=True).first()
        
        if existing_version:
            version_stats = HACCPDocument.objects.filter(
                company_id=company_id if company_id != 0 else None,
                product_type=product_type,
                year=current_year,
                version=existing_version
            ).aggregate(
                total_docs=Count('id'),
                completed_docs=Count('id', filter=Q(status='completed'))
            )
            
            if version_stats['total_docs'] < 4 or version_stats['completed_docs'] < 4:
                return JsonResponse({
                    'success': False,
                    'error': 'There is already an in-progress document set. Complete all 4 documents before creating a new version.'
                })
        
        completed_sets = HACCPDocument.objects.filter(
            company_id=company_id if company_id != 0 else None,
            product_type=product_type,
            year=current_year
        ).values('version').annotate(
            total_docs=Count('id'),
            completed_docs=Count('id', filter=Q(status='completed'))
        ).filter(total_docs=4, completed_docs=4).order_by('-version')
        
        last_completed_set = completed_sets.first()
        
        doc_types = ['product_description', 'flow_chart', 'hazard_analysis', 'ccp_summary']
        
        if not last_completed_set:
            new_version = 1
            
            for doc_type in doc_types:
                HACCPDocument.objects.create(
                    tenant=request.tenant,
                    company_id=company_id if company_id != 0 else None,
                    product_type=product_type,
                    document_type=doc_type,
                    year=current_year,
                    version=new_version,
                    status='not_started',
                    document_data={}
                )
            
            return JsonResponse({
                'success': True,
                'year': current_year,
                'version': new_version,
                'message': f'Created new document set version {new_version} with all 4 blank documents'
            })
        
        last_version = last_completed_set['version']
        new_version = last_version + 1
        
        for doc_type in doc_types:
            source_doc = HACCPDocument.objects.get(
                company_id=company_id if company_id != 0 else None,
                product_type=product_type,
                document_type=doc_type,
                year=current_year,
                version=last_version
            )
            
            HACCPDocument.objects.create(
                tenant=request.tenant,
                company_id=company_id if company_id != 0 else None,
                product_type=product_type,
                document_type=doc_type,
                year=current_year,
                version=new_version,
                status='in_progress',
                originated_date=source_doc.originated_date,
                originated_by=source_doc.originated_by,
                document_data=source_doc.document_data,
                approved_date=None,
                approved_by='',
                approved_signature=''
            )
        
        return JsonResponse({
            'success': True,
            'year': current_year,
            'version': new_version,
            'message': f'Created new document set version {new_version} with all 4 documents'
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False, 
            'error': str(e),
            'trace': traceback.format_exc()
        })


@login_required
def view_company_certificate(request, company_id, certificate_type):
    """View/edit company certificate"""
    if not request.tenant:
        return redirect('admin:index')
    
    company = get_object_or_404(Company, companyid=company_id)
    current_year = datetime.now().year
    
    cert = CompanyCertificate.objects.filter(
        company_id=company_id,
        year=current_year,
        certificate_type=certificate_type
    ).first()
    
    if not cert:
        cert = CompanyCertificate.objects.create(
            company=company,
            year=current_year,
            certificate_type=certificate_type
        )
    
    return render(request, 'core/haccp/company_certificate.html', {
        'company': company,
        'certificate': cert,
        'certificate_type_display': dict(CompanyCertificate.CERTIFICATE_TYPE_CHOICES)[certificate_type],
        'current_year': current_year
    })


def get_version_history(request, company_id, product_type, document_type):
    """Get all SET versions (not individual document versions) across years"""
    year_filter = request.GET.get('year')
    
    all_years = HACCPDocument.objects.filter(
        company_id=company_id if company_id != 0 else None,
        product_type=product_type
    ).values_list('year', flat=True).distinct().order_by('-year')
    
    query = HACCPDocument.objects.filter(
        company_id=company_id if company_id != 0 else None,
        product_type=product_type
    )
    
    if year_filter:
        query = query.filter(year=int(year_filter))
    
    version_sets = query.values('year', 'version').annotate(
        total_docs=Count('id'),
        completed_docs=Count('id', filter=Q(status='completed')),
        last_updated=Count('updated_at')
    ).order_by('-year', '-version')
    
    versions = []
    for v in version_sets:
        if v['total_docs'] == 4 and v['completed_docs'] == 4:
            status = 'completed'
            status_display = f"{v['completed_docs']}/4 Completed"
        elif v['total_docs'] == 4:
            status = 'in_progress'
            status_display = f"{v['completed_docs']}/4 Completed"
        else:
            status = 'in_progress'
            status_display = f"{v['completed_docs']}/{v['total_docs']} Completed"
        
        versions.append({
            'year': v['year'],
            'version': v['version'],
            'status': status,
            'status_display': status_display,
            'updated_at': datetime.now().isoformat(),
            'total_docs': v['total_docs'],
            'completed_docs': v['completed_docs']
        })
    
    return JsonResponse({
        'success': True,
        'years': list(all_years),
        'versions': versions
    })


def get_flow_chart_data(request, company_id, product_type):
    """Get flow chart boxes for syncing to hazard analysis"""
    current_year = datetime.now().year
    
    in_progress = HACCPDocument.objects.filter(
        company_id=company_id if company_id != 0 else None,
        product_type=product_type,
        document_type='flow_chart',
        year=current_year,
        status__in=['not_started', 'in_progress']
    ).order_by('-version').first()
    
    last_completed = HACCPDocument.objects.filter(
        company_id=company_id if company_id != 0 else None,
        product_type=product_type,
        document_type='flow_chart',
        year=current_year,
        status='completed'
    ).order_by('-version').first()
    
    doc = in_progress or last_completed
    
    if not doc:
        return JsonResponse({
            'success': False,
            'error': 'No flow chart found for current year'
        })
    
    flow_chart_data = doc.document_data.get('flowChart', {})
    boxes = flow_chart_data.get('boxes', [])
    
    return JsonResponse({
        'success': True,
        'boxes': boxes
    })


def get_hazard_analysis_data(request, company_id, product_type):
    """Get hazard analysis data for syncing to CCP summary"""
    current_year = datetime.now().year
    
    in_progress = HACCPDocument.objects.filter(
        company_id=company_id if company_id != 0 else None,
        product_type=product_type,
        document_type='hazard_analysis',
        year=current_year,
        status__in=['not_started', 'in_progress']
    ).order_by('-version').first()
    
    last_completed = HACCPDocument.objects.filter(
        company_id=company_id if company_id != 0 else None,
        product_type=product_type,
        document_type='hazard_analysis',
        year=current_year,
        status='completed'
    ).order_by('-version').first()
    
    doc = in_progress or last_completed
    
    if not doc:
        return JsonResponse({
            'success': False,
            'error': 'No hazard analysis found for current year'
        })
    
    steps = doc.document_data.get('steps', [])
    
    return JsonResponse({
        'success': True,
        'steps': steps
    })


@require_http_methods(["POST"])
def delete_haccp_version(request, company_id, product_type, document_type):
    """Delete a specific HACCP document version"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        year = int(data.get('year'))
        version = int(data.get('version'))
        
        doc = HACCPDocument.objects.get(
            company_id=company_id if company_id != 0 else None,
            product_type=product_type,
            document_type=document_type,
            year=year,
            version=version
        )
        
        doc.delete()
        
        return JsonResponse({'success': True})
        
    except HACCPDocument.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Version not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_haccp_version(request, company_id, product_type, document_type):
    """Get a specific HACCP document version data for copying"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        year = int(request.GET.get('year'))
        version = int(request.GET.get('version'))
        
        doc = HACCPDocument.objects.get(
            company_id=company_id if company_id != 0 else None,
            product_type=product_type,
            document_type=document_type,
            year=year,
            version=version
        )
        
        return JsonResponse({
            'success': True,
            'document': {
                'year': doc.year,
                'version': doc.version,
                'status': doc.status,
                'originated_date': doc.originated_date.isoformat() if doc.originated_date else None,
                'approved_date': doc.approved_date.isoformat() if doc.approved_date else None,
                'originated_by': doc.originated_by or '',
                'approved_by': doc.approved_by or '',
                'document_data': doc.document_data
            }
        })
        
    except HACCPDocument.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Version not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_master_product_types(request):
    """Get all product types that are active on at least one company"""
    active_types = CompanyProductType.objects.filter(
        is_active=True
    ).values_list('product_type', flat=True).distinct()
    
    return JsonResponse({
        'success': True,
        'active_types': list(active_types)
    })


def get_all_product_types(request):
    """Get all HACCP product types"""
    product_types = list(HACCPProductType.objects.filter(
        is_active=True
    ).values('slug', 'name'))
    
    return JsonResponse({
        'success': True,
        'product_types': product_types
    })


@require_http_methods(["POST"])
def add_product_type(request):
    """Add a new HACCP product type"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        from django.utils.text import slugify
        
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        
        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'})
        
        slug = slugify(name)
        
        existing = HACCPProductType.objects.filter(slug=slug).first()
        
        if existing:
            if existing.is_active:
                return JsonResponse({'success': False, 'error': 'Product type already exists'})
            else:
                existing.is_active = True
                existing.name = name
                existing.save()
                
                return JsonResponse({'success': True, 'slug': slug, 'name': name})
        
        HACCPProductType.objects.create(
            tenant=request.tenant,
            slug=slug,
            name=name,
            is_active=True
        )
        
        return JsonResponse({'success': True, 'slug': slug, 'name': name})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
def delete_product_type(request):
    """Soft delete a HACCP product type (mark as inactive)"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        slug = data.get('slug')
        
        if not slug:
            return JsonResponse({'success': False, 'error': 'Slug is required'})
        
        HACCPProductType.objects.filter(slug=slug).update(is_active=False)
        CompanyProductType.objects.filter(product_type=slug).update(is_active=False)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_inactive_product_types(request):
    """Get all inactive product types (recycle bin)"""
    inactive_types = list(HACCPProductType.objects.filter(
        is_active=False
    ).values('slug', 'name', 'updated_at'))
    
    return JsonResponse({
        'success': True,
        'product_types': inactive_types
    })


@require_http_methods(["POST"])
def restore_product_type(request):
    """Restore a soft-deleted product type"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        slug = data.get('slug')
        
        if not slug:
            return JsonResponse({'success': False, 'error': 'Slug is required'})
        
        HACCPProductType.objects.filter(slug=slug).update(is_active=True)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
def set_haccp_owner(request, company_id):
    """Set HACCP process owner for a company"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        company = get_object_or_404(Company, companyid=company_id)
        
        if user_id:
            user = get_object_or_404(User, id=user_id)
            CompanyHACCPOwner.objects.update_or_create(
                company=company,
                defaults={'user': user}
            )
        else:
            CompanyHACCPOwner.objects.filter(company=company).delete()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_company_certificates(request, company_id):
    """Get certificate status for a company"""
    current_year = datetime.now().year
    
    certificates = {}
    for cert_type, _ in CompanyCertificate.CERTIFICATE_TYPE_CHOICES:
        cert = CompanyCertificate.objects.filter(
            company_id=company_id,
            year=current_year,
            certificate_type=cert_type
        ).first()
        
        certificates[cert_type] = {
            'is_completed': cert.is_completed if cert else False,
            'date_issued': cert.date_issued.isoformat() if cert and cert.date_issued else None,
            'signed_by': cert.signed_by if cert else None
        }
    
    return JsonResponse({
        'success': True,
        'certificates': certificates
    })


@require_http_methods(["POST"])
def save_company_certificate(request, company_id):
    """Save company certificate"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        cert_type = data.get('certificate_type')
        current_year = datetime.now().year
        
        company = get_object_or_404(Company, companyid=company_id)
        
        cert, created = CompanyCertificate.objects.get_or_create(
            company=company,
            year=current_year,
            certificate_type=cert_type
        )
        
        cert.date_issued = data.get('date_issued') or None
        cert.signed_by = data.get('signed_by', '')
        cert.signature = data.get('signature', '')
        cert.is_completed = data.get('is_completed', False)
        cert.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})