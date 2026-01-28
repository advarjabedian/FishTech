from django.db import models
from django.contrib.auth.models import User
from threading import local

_thread_locals = local()

def get_current_tenant():
    return getattr(_thread_locals, 'tenant', None)

def set_current_tenant(tenant):
    _thread_locals.tenant = tenant

class TenantManager(models.Manager):
    """Manager that automatically filters by current tenant"""
    
    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant:
            return qs.filter(tenant=tenant)
        return qs

class TenantModel(models.Model):
    """Abstract base model for tenant-scoped models"""
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)
    
    objects = TenantManager()
    all_objects = models.Manager()  # Access all tenants if needed
    
    class Meta:
        abstract = True

class Tenant(models.Model):
    """Represents each fish factory customer"""
    name = models.CharField(max_length=255)  # Company name
    subdomain = models.CharField(max_length=63, unique=True)  # e.g., 'goldenstateseafood'
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class TenantUser(models.Model):
    """Links Django users to tenants"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.user.username} - {self.tenant.name}"

class Company(TenantModel):
    """Company/facility within a tenant"""
    companyid = models.AutoField(primary_key=True)
    companyname = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    zipcode = models.CharField(max_length=10, blank=True)
    
    class Meta:
        db_table = 'company'
        unique_together = [['tenant', 'companyname']]
    
    def __str__(self):
        return self.companyname
    

class HACCPProductType(TenantModel):
    """Available HACCP product types"""
    slug = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['tenant', 'slug']]
    
    def __str__(self):
        return self.name

class CompanyProductType(models.Model):
    """Which product types are active for each company"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    product_type = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = [['company', 'product_type']]

class CompanyHACCPOwner(models.Model):
    """HACCP process owner for each company"""
    company = models.OneToOneField(Company, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

class HACCPDocument(TenantModel):
    """HACCP documents"""
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, help_text="NULL = tenant master set")
    product_type = models.CharField(max_length=100)
    document_type = models.CharField(max_length=100)
    year = models.IntegerField()
    version = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    document_data = models.JSONField(default=dict)
    
    originated_date = models.DateField(null=True, blank=True)
    originated_by = models.CharField(max_length=255, blank=True)
    approved_date = models.DateField(null=True, blank=True)
    approved_by = models.CharField(max_length=255, blank=True)
    approved_signature = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['tenant', 'company', 'product_type', 'document_type', 'year', 'version']]

class CompanyCertificate(models.Model):
    """Company HACCP certificates"""
    CERTIFICATE_TYPE_CHOICES = [
        ('haccp_certificate', 'HACCP Certificate'),
        ('letter_of_guarantee', 'Letter of Guarantee'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    year = models.IntegerField()
    certificate_type = models.CharField(max_length=50, choices=CERTIFICATE_TYPE_CHOICES)
    date_issued = models.DateField(null=True, blank=True)
    signed_by = models.CharField(max_length=255, blank=True)
    signature = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = [['company', 'year', 'certificate_type']]