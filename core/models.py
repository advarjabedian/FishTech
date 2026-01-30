from django.db import models
from django.contrib.auth.models import User as DjangoUser
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
    created_at = models.DateField(null=True, blank=True, help_text="SOP effective date - only shows in inspections on/after this date")
    
    def __str__(self):
        return self.name

class TenantUser(models.Model):
    """Links Django users to tenants"""
    user = models.OneToOneField(DjangoUser, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    is_admin = models.BooleanField(default=False)
    
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
    logo = models.TextField(blank=True)  # Base64 encoded logo
    
    class Meta:
        db_table = 'company'
        unique_together = [['tenant', 'companyname']]
    
    def __str__(self):
        return self.companyname


class User(TenantModel):
    """Custom user model for business logic"""
    userid = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    cellnumber = models.CharField(max_length=50, null=True, blank=True)
    usercode = models.CharField(max_length=100, null=True, blank=True)
    commission = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'core_user'
    
    def __str__(self):
        return self.name if self.name else f"User #{self.id}"
    

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

class CompanyProductType(TenantModel):
    """Which product types are active for each company"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    product_type = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = [['tenant', 'company', 'product_type']]

class CompanyHACCPOwner(TenantModel):
    """HACCP process owner for each company"""
    company = models.OneToOneField(Company, on_delete=models.CASCADE)
    user = models.ForeignKey(DjangoUser, on_delete=models.SET_NULL, null=True)

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




# Daily Inspections Models

class Zone(TenantModel):
    """Inspection zones for each company"""
    name = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = [['tenant', 'company', 'name']]
    
    def __str__(self):
        return f"{self.name} ({self.company.companyname})"


class SOP(TenantModel):
    """Standard Operating Procedures for inspections"""
    sop_did = models.IntegerField()
    description = models.CharField(max_length=255, blank=True)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, null=True, blank=True)
    pre = models.BooleanField(default=False)  # Pre-Op shift
    mid = models.BooleanField(default=False)  # Mid-Day shift
    post = models.BooleanField(default=False)  # Post-Op shift
    input_required = models.BooleanField(default=False)  # Requires data input
    image_required = models.BooleanField(default=False)  # Requires image
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['tenant', 'company', 'sop_did']]
    
    def __str__(self):
        return f"SOP {self.sop_did}: {self.description}" if self.description else f"SOP {self.sop_did}"


class SOPParent(TenantModel):
    """Parent record for a shift inspection"""
    SHIFT_CHOICES = [
        ('Pre-Op', 'Pre-Op'),
        ('Mid-Day', 'Mid-Day'),
        ('Post-Op', 'Post-Op'),
    ]
    
    date = models.DateField()
    time = models.TimeField()
    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    user_inspected = models.ForeignKey(DjangoUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='inspections')
    user_verified = models.ForeignKey(DjangoUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='verifications')
    completed = models.BooleanField(default=False)
    
    # Inspector signature
    inspector_name = models.CharField(max_length=100, blank=True)
    inspector_signature = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Verification
    verified = models.BooleanField(default=False)
    verifier_name = models.CharField(max_length=100, blank=True)
    verifier_signature = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = [['tenant', 'company', 'date', 'shift']]
    
    def __str__(self):
        return f"{self.company.companyname} - {self.shift} - {self.date}"


class SOPChild(models.Model):
    """Individual SOP item result within a shift inspection"""
    sop_parent = models.ForeignKey(SOPParent, on_delete=models.CASCADE, related_name='children')
    sop_did = models.IntegerField()
    passed = models.BooleanField(default=False)
    failed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    deviation_reason = models.CharField(max_length=500, blank=True)
    corrective_action = models.TextField(blank=True)
    image = models.TextField(blank=True)  # Base64 image data
    
    class Meta:
        unique_together = [['sop_parent', 'sop_did']]
    
    def __str__(self):
        status = "PASS" if self.passed else ("FAIL" if self.failed else "N/A")
        return f"SOP {self.sop_did} - {status}"


class CompanyOperationConfig(TenantModel):
    """Configuration for daily inspections per company"""
    company = models.OneToOneField(Company, on_delete=models.CASCADE)
    start_date = models.DateField(null=True, blank=True)
    monday = models.BooleanField(default=True)
    tuesday = models.BooleanField(default=True)
    wednesday = models.BooleanField(default=True)
    thursday = models.BooleanField(default=True)
    friday = models.BooleanField(default=True)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)
    monitor_user = models.ForeignKey(DjangoUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='monitored_companies')
    verifier_user = models.ForeignKey(DjangoUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_companies')
    verifier_signature = models.TextField(blank=True)
    monitor_signature = models.TextField(blank=True)
    
    def is_operating_day(self, weekday):
        """Check if company operates on given weekday (0=Monday, 6=Sunday)"""
        days = [self.monday, self.tuesday, self.wednesday, self.thursday, 
                self.friday, self.saturday, self.sunday]
        return days[weekday]


class CompanyHoliday(TenantModel):
    """Non-operating days for companies"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    date = models.DateField()
    
    class Meta:
        unique_together = [['tenant', 'company', 'date']]


class CompanyCertificate(TenantModel):
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
        unique_together = [['tenant', 'company', 'year', 'certificate_type']]


class UserCompany(TenantModel):
    """Associates users with companies"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = [['tenant', 'user', 'company']]