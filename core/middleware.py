from django.utils.deprecation import MiddlewareMixin
from .models import TenantUser, set_current_tenant

class TenantMiddleware(MiddlewareMixin):
    """Automatically set current tenant based on logged-in user"""
    
    def process_request(self, request):
        request.tenant = None
        set_current_tenant(None)
        
        if request.user.is_authenticated:
            try:
                tenant_user = TenantUser.objects.select_related('tenant').get(user=request.user)
                request.tenant = tenant_user.tenant
                set_current_tenant(tenant_user.tenant)
            except TenantUser.DoesNotExist:
                pass
        
        return None