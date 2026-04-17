from django.contrib import admin
from .models import (
    Tenant, TenantUser,
)

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'subdomain', 'is_active', 'created_at']
    search_fields = ['name', 'subdomain']

@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'tenant']
    list_filter = ['tenant']
