from django.utils.deprecation import MiddlewareMixin
from .models import TenantUser, Company, set_current_tenant

class TenantMiddleware(MiddlewareMixin):
    """Automatically set current tenant based on logged-in user"""
    
    def process_request(self, request):
        request.tenant = None
        request.companies = []
        request.selected_company = None
        set_current_tenant(None)
        
        if request.user.is_authenticated:
            try:
                tenant_user = TenantUser.objects.select_related('tenant').get(user=request.user)
                request.tenant = tenant_user.tenant
                set_current_tenant(tenant_user.tenant)
                
                # Get all companies for this tenant
                request.companies = list(Company.objects.filter(tenant=tenant_user.tenant).order_by('companyname'))
                
                # Get selected company from session
                company_id = request.session.get('selected_company_id')
                
                # Only update session from GET param on the operations hub page
                if request.path == '/operations/' and request.GET.get('company_id'):
                    company_id = request.GET.get('company_id')
                
                if company_id:
                    request.selected_company = Company.objects.filter(
                        tenant=tenant_user.tenant, 
                        companyid=company_id
                    ).first()
                
                if not request.selected_company and request.companies:
                    request.selected_company = request.companies[0]
                
                # Store in session for persistence
                if request.selected_company:
                    request.session['selected_company_id'] = request.selected_company.companyid
                    
            except TenantUser.DoesNotExist:
                pass
        
        return None