from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from .models import TenantUser, set_current_tenant

class TenantMiddleware(MiddlewareMixin):
    """Automatically set current tenant based on logged-in user."""

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

        if (
            settings.ENFORCE_SUBSCRIPTION_BILLING
            and request.user.is_authenticated
            and request.tenant
            and not request.user.is_superuser
            and not request.tenant.is_subscription_valid()
        ):
            allowed_prefixes = (
                "/billing/",
                "/logout/",
                "/static/",
                "/media/",
                "/admin/",
                "/api/billing/webhook/",
            )
            if not request.path.startswith(allowed_prefixes):
                return redirect("billing_page")

        return None
