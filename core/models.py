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
    SUBSCRIPTION_STATUS_CHOICES = [
        ('trialing', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('unpaid', 'Unpaid'),
    ]
    
    name = models.CharField(max_length=255)  # Company name
    subdomain = models.CharField(max_length=63, unique=True)  # e.g., 'goldenstateseafood'
    is_active = models.BooleanField(default=True)
    created_at = models.DateField(null=True, blank=True, help_text="SOP effective date - only shows in inspections on/after this date")
    
    # Stripe billing fields
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    subscription_status = models.CharField(max_length=20, choices=SUBSCRIPTION_STATUS_CHOICES, default='trialing')
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_ends_at = models.DateTimeField(null=True, blank=True)
    # Email settings
    reply_to_email = models.EmailField(blank=True, null=True, help_text="Customer replies go here")
    reply_to_name = models.CharField(max_length=255, blank=True, null=True, help_text="Display name for reply-to")
    
    def __str__(self):
        return self.name
    
    def is_subscription_valid(self):
        """Check if tenant has valid subscription or is in trial"""
        from django.utils import timezone
        if self.subscription_status == 'active':
            return True
        if self.subscription_status == 'trialing' and self.trial_ends_at:
            return timezone.now() < self.trial_ends_at
        return False
    
    def days_remaining_in_trial(self):
        """Get days remaining in trial"""
        from django.utils import timezone
        if self.subscription_status == 'trialing' and self.trial_ends_at:
            delta = self.trial_ends_at - timezone.now()
            return max(0, delta.days)
        return 0

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


# =============================================================================
# DOCUMENTS MODULE MODELS
# =============================================================================

class Customer(TenantModel):
    """Customer records"""
    customer_id = models.IntegerField()  # External/legacy ID
    name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    zipcode = models.CharField(max_length=20, blank=True)
    ship_address = models.CharField(max_length=255, blank=True)
    ship_city = models.CharField(max_length=100, blank=True)
    ship_state = models.CharField(max_length=50, blank=True)
    ship_zipcode = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'documents_customer'
        unique_together = [['tenant', 'customer_id']]
    
    def __str__(self):
        return self.name


class CustomerEmail(TenantModel):
    """Saved email addresses for customers"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='emails')
    email = models.EmailField()
    label = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'documents_customer_email'
        unique_together = [['tenant', 'customer', 'email']]


class Vendor(TenantModel):
    """Vendor records"""
    vendor_id = models.IntegerField()  # External/legacy ID
    name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    zipcode = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'documents_vendor'
        unique_together = [['tenant', 'vendor_id']]
    
    def __str__(self):
        return self.name


class VendorEmail(TenantModel):
    """Saved email addresses for vendors"""
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='emails')
    email = models.EmailField()
    label = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'documents_vendor_email'
        unique_together = [['tenant', 'vendor', 'email']]


class SO(TenantModel):
    """Sales Order header"""
    soid = models.IntegerField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_orders')
    customerid = models.IntegerField(null=True, blank=True)  # Legacy ID reference
    
    # Dates
    dispatchdate = models.DateField(null=True, blank=True)
    deadline = models.CharField(max_length=50, blank=True)
    
    # Billing info
    billto1 = models.CharField(max_length=255, blank=True)
    billto2 = models.CharField(max_length=255, blank=True)
    billto3 = models.CharField(max_length=255, blank=True)
    billto4 = models.CharField(max_length=255, blank=True)
    billing = models.CharField(max_length=100, blank=True)
    
    # Shipping info
    shipto1 = models.CharField(max_length=255, blank=True)
    shipto2 = models.CharField(max_length=255, blank=True)
    shipto3 = models.CharField(max_length=255, blank=True)
    shipto4 = models.CharField(max_length=255, blank=True)
    
    # Route info
    route = models.IntegerField(null=True, blank=True)
    routeid = models.IntegerField(null=True, blank=True)
    
    # Financials
    totalamount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payamount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    creditamount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    paid = models.CharField(max_length=50, blank=True)
    pos = models.CharField(max_length=50, blank=True)
    
    # Status
    invoiced = models.CharField(max_length=50, blank=True)
    filed = models.CharField(max_length=50, blank=True)
    priority = models.IntegerField(null=True, blank=True)
    totalunits = models.IntegerField(null=True, blank=True)
    lockorder = models.IntegerField(null=True, blank=True)
    
    # Delivery
    deliverwindowopen = models.CharField(max_length=50, blank=True)
    deliverwindowclose = models.CharField(max_length=50, blank=True)
    
    # Other
    customerpo = models.CharField(max_length=100, blank=True)
    comments = models.TextField(blank=True)
    savetime = models.CharField(max_length=50, blank=True)
    oddball = models.IntegerField(null=True, blank=True)
    dba = models.IntegerField(null=True, blank=True)
    onlineorderid = models.IntegerField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'documents_so'
        unique_together = [['tenant', 'soid']]
    
    def __str__(self):
        return f"SO-{self.soid}"


class SOD(TenantModel):
    """Sales Order Detail / line items"""
    sodid = models.IntegerField()
    so = models.ForeignKey(SO, on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    soid = models.IntegerField(null=True, blank=True)  # Legacy reference
    
    # Product info
    productid = models.IntegerField(null=True, blank=True)
    descriptionmemo = models.TextField(blank=True)
    origin = models.IntegerField(null=True, blank=True)
    category = models.IntegerField(null=True, blank=True)
    
    # Units
    unittype = models.IntegerField(null=True, blank=True)
    unitsize = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    orderedunits = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unitsshipped = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    weightshipped = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    packsshipped = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    
    # Pricing
    salesprice = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    
    # Status
    priority = models.IntegerField(null=True, blank=True)
    complete = models.IntegerField(null=True, blank=True)
    edit = models.CharField(max_length=50, blank=True)
    
    # Other
    specialinstructions = models.TextField(blank=True)
    salesrep = models.CharField(max_length=100, blank=True)
    company = models.CharField(max_length=255, blank=True)
    sfpnumber = models.CharField(max_length=100, blank=True)
    crew = models.CharField(max_length=100, blank=True)
    onlineorderdid = models.IntegerField(null=True, blank=True)
    supc = models.CharField(max_length=100, blank=True)
    unitpriceon = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'documents_sod'
        unique_together = [['tenant', 'sodid']]
    
    def __str__(self):
        return f"SOD-{self.sodid}"


class PO(TenantModel):
    """Purchase Order header"""
    poid = models.IntegerField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_orders')
    vendorid = models.IntegerField(null=True, blank=True)  # Legacy ID reference
    buyer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_orders')
    
    # Dates
    orderdate = models.DateField(null=True, blank=True)
    receivedate = models.DateField(null=True, blank=True)
    receivetime = models.CharField(max_length=50, blank=True)
    
    # Reference numbers
    vendorref = models.CharField(max_length=100, blank=True)
    awb = models.CharField(max_length=100, blank=True)  # Air waybill
    
    # Financials
    totalcost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payment = models.CharField(max_length=50, blank=True)
    paid = models.CharField(max_length=50, blank=True)
    credit = models.CharField(max_length=50, blank=True)
    account = models.CharField(max_length=100, blank=True)
    
    # Receiving - temperatures
    temperature = models.CharField(max_length=50, blank=True)
    trailertemp = models.CharField(max_length=50, blank=True)
    top_temp = models.CharField(max_length=50, blank=True)
    middle_temp = models.CharField(max_length=50, blank=True)
    bottom_temp = models.CharField(max_length=50, blank=True)
    trailer_temp_before = models.CharField(max_length=50, blank=True)
    trailer_temp_after = models.CharField(max_length=50, blank=True)
    
    # Receiving - inspection
    receiver = models.CharField(max_length=100, blank=True)
    datalogreq = models.CharField(max_length=50, blank=True)
    datalog = models.CharField(max_length=50, blank=True)
    datalogrev = models.CharField(max_length=50, blank=True)
    truckcondition = models.CharField(max_length=100, blank=True)
    palletcondition = models.CharField(max_length=100, blank=True)
    containercondition = models.CharField(max_length=100, blank=True)
    iceadequate = models.CharField(max_length=50, blank=True)
    shellfishTag = models.CharField(max_length=100, blank=True)
    scombroidice = models.CharField(max_length=50, blank=True)
    shuckedcc = models.CharField(max_length=50, blank=True)
    frozenshell = models.CharField(max_length=50, blank=True)
    labels = models.CharField(max_length=100, blank=True)
    country_origin = models.CharField(max_length=50, blank=True)
    seal_num = models.CharField(max_length=100, blank=True)
    disposition_good = models.BooleanField(default=True)
    
    # Review/verification
    reviewed = models.CharField(max_length=50, blank=True)
    verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.CharField(max_length=100, blank=True)
    verified_signature = models.TextField(blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    received_by = models.CharField(max_length=100, blank=True)
    
    # Other
    memo = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    padding = models.CharField(max_length=100, blank=True)
    invoicecopyrequest = models.CharField(max_length=50, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'documents_po'
        unique_together = [['tenant', 'poid']]
    
    def __str__(self):
        return f"PO-{self.poid}"


class POD(TenantModel):
    """Purchase Order Detail / line items"""
    podid = models.IntegerField()
    po = models.ForeignKey(PO, on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    poid = models.IntegerField(null=True, blank=True)  # Legacy reference
    
    # Product info
    productid = models.IntegerField(null=True, blank=True)
    descriptionmemo = models.TextField(blank=True)
    category = models.IntegerField(null=True, blank=True)
    origin = models.IntegerField(null=True, blank=True)
    
    # Lot tracking
    vendorlot = models.CharField(max_length=100, blank=True)
    packdate = models.DateField(null=True, blank=True)
    shelflife = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Units
    unittype = models.IntegerField(null=True, blank=True)
    packsize = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    fixed = models.IntegerField(null=True, blank=True)
    
    # Quantities in
    unitsin = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    weightin = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unitsordered = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    
    # Quantities out/allocated
    unitsallocated = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unitsout = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    weightout = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    weightbalance = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    dripout = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    billedweight = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    
    # Storage
    storageid = models.IntegerField(null=True, blank=True)
    unitsstored = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unitsrequested = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unitsretrieved = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    
    # Pricing
    unitprice = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    origprice = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    promoprice = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    costverified = models.CharField(max_length=50, blank=True)
    costpad = models.CharField(max_length=50, blank=True)
    
    # Claims
    claimamount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reasonforclaim = models.CharField(max_length=255, blank=True)
    
    # Status
    promotion = models.CharField(max_length=100, blank=True)
    companyid = models.IntegerField(null=True, blank=True)
    derived = models.IntegerField(null=True, blank=True)
    flagged = models.IntegerField(null=True, blank=True)
    hidden = models.IntegerField(null=True, blank=True)
    ogpodid = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'documents_pod'
        unique_together = [['tenant', 'podid']]
    
    def __str__(self):
        return f"POD-{self.podid}"


class Receipt(TenantModel):
    """Email receipts from vendors"""
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    email_sender = models.CharField(max_length=255, blank=True)
    email_subject = models.CharField(max_length=500, blank=True)
    receipt_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'documents_receipt'
    
    def __str__(self):
        return f"Receipt {self.id} - {self.email_subject[:50] if self.email_subject else 'No subject'}"
    

class DocumentFile(TenantModel):
    """Tracks uploaded files for SO/PO/POD/Customer/Vendor"""
    DOCUMENT_TYPE_CHOICES = [
        ('so', 'Sales Order'),
        ('po', 'Purchase Order'),
        ('pod', 'POD'),
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('receipt', 'Receipt'),
    ]
    
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    document_id = models.CharField(max_length=50)  # The SOID, POID, etc.
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_type = models.CharField(max_length=50, blank=True)  # pdf, image, etc.
    file_size = models.IntegerField(null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'documents_file'
        unique_together = [['tenant', 'document_type', 'document_id', 'filename']]
    
    def __str__(self):
        return f"{self.document_type.upper()}-{self.document_id}: {self.filename}"
    

class TenantEmail(TenantModel):
    """Tenant-wide email address book"""
    email = models.EmailField()
    label = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'documents_tenant_email'
        unique_together = [['tenant', 'email']]
    
    def __str__(self):
        return f"{self.email} ({self.label})" if self.label else self.email