from django.contrib import admin
from .models import (
    Tenant, TenantUser, HACCPProductType,
    CompanyProductType, CompanyHACCPOwner, HACCPDocument,
    CompanyCertificate
)

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'subdomain', 'is_active', 'created_at']
    search_fields = ['name', 'subdomain']

@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'tenant']
    list_filter = ['tenant']

@admin.register(HACCPProductType)
class HACCPProductTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active']

@admin.register(CompanyProductType)
class CompanyProductTypeAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'product_type', 'is_active']
    list_filter = ['tenant', 'is_active']

@admin.register(HACCPDocument)
class HACCPDocumentAdmin(admin.ModelAdmin):
    list_display = ['product_type', 'document_type', 'year', 'version', 'status']
    list_filter = ['status', 'year', 'product_type']

@admin.register(CompanyCertificate)
class CompanyCertificateAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'certificate_type', 'year', 'is_completed']
    list_filter = ['certificate_type', 'year', 'is_completed']
