from django.utils.deprecation import MiddlewareMixin
from .models import TenantUser, Company, set_current_tenant

class TenantMiddleware(MiddlewareMixin):
    """Automatically set current tenant based on logged-in user.
    Each tenant = one company/facility. Auto-selects the single company."""

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

                # Auto-select the single company for this tenant
                company = Company.objects.filter(tenant=tenant_user.tenant).first()
                if company:
                    request.companies = [company]
                    request.selected_company = company
                    request.session['selected_company_id'] = company.companyid

            except TenantUser.DoesNotExist:
                pass

        return None
