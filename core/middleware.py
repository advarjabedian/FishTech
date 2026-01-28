from django.utils.deprecation import MiddlewareMixin
from .models import TenantUser

class TenantMiddleware(MiddlewareMixin):
    """Automatically set current tenant based on logged-in user"""
    
    def process_request(self, request):
        request.tenant = None
        
        if request.user.is_authenticated:
            try:
                tenant_user = TenantUser.objects.select_related('tenant').get(user=request.user)
                request.tenant = tenant_user.tenant
            except TenantUser.DoesNotExist:
                pass
        
        return None