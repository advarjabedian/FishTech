from django.db import models
from django.contrib.auth.models import User as DjangoUser
from threading import local
from django.conf import settings
import uuid

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
    
    # Inbound email settings (IMAP)
    inbound_email_address = models.EmailField(blank=True, null=True, help_text="Email to check for orders/voicemails")
    inbound_email_password = models.CharField(max_length=255, blank=True, help_text="App password")
    inbound_email_imap_server = models.CharField(max_length=255, blank=True, default='imap.gmail.com')
    
    # Outbound email SMTP settings (per-tenant)
    smtp_host = models.CharField(max_length=255, blank=True, help_text="e.g. smtp-mail.outlook.com")
    smtp_port = models.PositiveIntegerField(default=587, blank=True, null=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_user = models.EmailField(blank=True, help_text="SMTP login email")
    smtp_password = models.CharField(max_length=255, blank=True, help_text="SMTP login password")
    smtp_from_email = models.EmailField(blank=True, help_text="From address for outbound emails")

    # Twilio SMS settings
    twilio_account_sid = models.CharField(max_length=100, blank=True)
    twilio_auth_token = models.CharField(max_length=100, blank=True)
    twilio_phone_number = models.CharField(max_length=20, blank=True, help_text="e.g. +18555975969")

    # Facility info (formerly on Company)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    zipcode = models.CharField(max_length=10, blank=True)
    logo = models.TextField(blank=True)

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
    signature = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.tenant.name}"


class Lead(models.Model):
    """Sales lead tracking for platform admin"""
    STAGE_CHOICES = [
        ('prospect', 'Prospect'),
        ('contacted', 'Contacted'),
        ('demo', 'Demo Scheduled'),
        ('proposal', 'Proposal Sent'),
        ('negotiation', 'Negotiation'),
        ('won', 'Won'),
        ('lost', 'Lost'),
    ]

    company_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='prospect')
    contract_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    last_contacted = models.DateField(null=True, blank=True)
    next_followup = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_followup', '-updated_at']

    def __str__(self):
        return f"{self.company_name} - {self.get_stage_display()}"

class TenantDocument(models.Model):
    """Signable documents associated with a tenant"""
    DOCUMENT_TYPES = [
        ('subscription_agreement', 'Subscription Agreement'),
        ('privacy_policy', 'Privacy Policy'),
        ('sla', 'Service Level Agreement'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    signing_token = models.UUIDField(default=uuid.uuid4, unique=True)
    is_signed = models.BooleanField(default=False)
    signer_name = models.CharField(max_length=255, blank=True)
    signer_title = models.CharField(max_length=255, blank=True)
    signature = models.TextField(blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['tenant', 'document_type']]

    def __str__(self):
        return f"{self.tenant.name} - {self.get_document_type_display()}"




class User(TenantModel):
    """Custom user model for business logic"""
    userid = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    cellnumber = models.CharField(max_length=50, null=True, blank=True)
    usercode = models.CharField(max_length=100, null=True, blank=True)
    commission = models.IntegerField(null=True, blank=True)
    signature = models.TextField(blank=True)

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
    """Which HACCP product types are active for this tenant"""

    product_type = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [['tenant', 'product_type']]

class CompanyHACCPOwner(TenantModel):
    """HACCP process owner for the tenant"""

    user = models.ForeignKey(DjangoUser, on_delete=models.SET_NULL, null=True)

class HACCPDocument(TenantModel):
    """HACCP documents"""
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    

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
        unique_together = [['tenant', 'product_type', 'document_type', 'year', 'version']]




# Daily Inspections Models

class Zone(TenantModel):
    """Inspection zones"""
    name = models.CharField(max_length=255)


    class Meta:
        unique_together = [['tenant', 'name']]

    def __str__(self):
        return self.name


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

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['tenant', 'sop_did']]
    
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
        unique_together = [['tenant', 'date', 'shift']]

    def __str__(self):
        return f"{self.tenant.name} - {self.shift} - {self.date}"


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
    """Configuration for daily inspections"""

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
    """Non-operating days"""

    date = models.DateField()

    class Meta:
        unique_together = [['tenant', 'date']]


class CompanyCertificate(TenantModel):
    """Company HACCP certificates"""
    CERTIFICATE_TYPE_CHOICES = [
        ('haccp_certificate', 'HACCP Certificate'),
        ('letter_of_guarantee', 'Letter of Guarantee'),
    ]
    

    year = models.IntegerField()
    certificate_type = models.CharField(max_length=50, choices=CERTIFICATE_TYPE_CHOICES)
    date_issued = models.DateField(null=True, blank=True)
    signed_by = models.CharField(max_length=255, blank=True)
    signature = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        unique_together = [['tenant', 'year', 'certificate_type']]




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
    is_retail = models.BooleanField(default=False, help_text="Retail customer - items appear on the Fish Market page")
    created_at = models.DateTimeField(auto_now_add=True)
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        db_table = 'documents_customer'
        unique_together = [['tenant', 'customer_id']]

    def __str__(self):
        return self.name


class ContactEmail(TenantModel):
    """Saved email addresses for customers, vendors, or tenant-wide use"""
    CONTACT_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('tenant', 'Tenant'),
    ]
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPE_CHOICES)
    entity_id = models.IntegerField(null=True, blank=True, help_text="Customer or Vendor ID (null for tenant-wide)")
    email = models.EmailField()
    label = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contact_email'
        unique_together = [['tenant', 'contact_type', 'entity_id', 'email']]

    def __str__(self):
        return f"{self.email} ({self.label})" if self.label else self.email


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
    # BlueTrace fields
    vendor_type = models.CharField(max_length=50, blank=True, help_text="e.g. Dealer, Exporter, Harvester")
    cert = models.CharField(max_length=255, blank=True, help_text="Certification number")
    phone_extension = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=50, blank=True)
    billing_email = models.EmailField(blank=True)
    mailing_address = models.CharField(max_length=255, blank=True)
    mailing_city = models.CharField(max_length=100, blank=True)
    mailing_state = models.CharField(max_length=50, blank=True)
    mailing_zipcode = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'documents_vendor'
        unique_together = [['tenant', 'vendor_id']]

    def __str__(self):
        return self.name

    @property
    def full_mailing_address(self):
        parts = [self.mailing_address or self.address]
        city_state = ', '.join(filter(None, [self.mailing_city or self.city, self.mailing_state or self.state]))
        if city_state:
            parts.append(city_state)
        zc = self.mailing_zipcode or self.zipcode
        if zc:
            parts[-1] = parts[-1] + ' ' + zc if parts else zc
        return ', '.join(filter(None, parts))








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
    



class License(TenantModel):
    """Business licenses"""
    filename = models.CharField(max_length=255)
    title = models.CharField(max_length=255)

    issuance_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    managing_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'documents_license'
    
    def __str__(self):
        return self.title


class Vehicle(TenantModel):
    """Fleet vehicles"""
    year = models.IntegerField(null=True, blank=True)
    make = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    vin = models.CharField(max_length=50, blank=True)
    license_plate = models.CharField(max_length=20, blank=True)
    number = models.CharField(max_length=20, blank=True)  # Vehicle number
    driver = models.CharField(max_length=100, blank=True)
    dmv_renewal_date = models.DateField(null=True, blank=True)
    company = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, blank=True)  # Active/Inactive
    title = models.CharField(max_length=100, blank=True)
    carb_number = models.CharField(max_length=100, blank=True)
    dash_cam = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'documents_vehicle'
    
    def __str__(self):
        return f"{self.year} {self.make} {self.model} - {self.license_plate}"


class InboundMessage(TenantModel):
    """Inbound messages from email, voicemail, or SMS"""
    SOURCE_CHOICES = [
        ('email', 'Email'),
        ('voicemail', 'Voicemail'),
        ('sms', 'SMS/Text'),
    ]
    
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='email')
    received_at = models.DateTimeField(null=True, blank=True)
    subject = models.CharField(max_length=500, blank=True)
    sender = models.CharField(max_length=255, blank=True)
    sender_phone = models.CharField(max_length=50, blank=True)
    sender_name = models.CharField(max_length=255, blank=True)
    
    # Content
    body = models.TextField(blank=True)  # Original email/SMS body
    transcription = models.TextField(blank=True)  # AI transcription for voicemails
    
    # Attachments
    filename = models.CharField(max_length=255, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    duration = models.IntegerField(null=True, blank=True)  # Voicemail duration in seconds
    
    # Workflow
    status = models.CharField(max_length=50, default='Unassigned')
    assigned_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inbound_message'
    
    def __str__(self):
        return f"{self.get_source_display()} {self.id} - {self.subject[:50] if self.subject else self.sender}"
    

class CustomerProfile(TenantModel):
    """Order profile items for a customer — what they regularly order"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='profiles')
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True, related_name='assignments')

    # Item info
    profile_did = models.IntegerField(null=True, blank=True)  # Legacy line ID
    comp_item_id = models.IntegerField(null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    instruction = models.TextField(blank=True)
    
    # Pricing / units
    unit_type = models.CharField(max_length=50, blank=True)
    pack_size = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sales_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    comp_price_id = models.IntegerField(null=True, blank=True)
    origin_id = models.IntegerField(null=True, blank=True)
    
    # Flags
    is_active = models.BooleanField(default=True)

    # Retail display fields (used when customer.is_retail=True)
    category = models.CharField(max_length=100, blank=True)
    image = models.TextField(blank=True)  # Base64 encoded image
    sort_order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'profile_customerprofile'
        ordering = ['sort_order', 'description']

    def __str__(self):
        return f"{self.customer.name} - {self.description}"


class ProductSize(models.Model):
    """Size variants for a CustomerProfile item (e.g. 1oz, 2oz, 4oz)."""
    profile = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='sizes')
    name = models.CharField(max_length=50)  # e.g. "1oz", "2oz"
    price = models.DecimalField(max_digits=10, decimal_places=2)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'profile_productsize'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f"{self.profile.description} - {self.name} (${self.price})"


def product_image_path(instance, filename):
    """Upload to: products/{product_id}/{slot}{ext}"""
    import os
    ext = os.path.splitext(filename)[1]
    return f"products/{instance.product_id}/{instance.slot}{ext}"


class ProductImage(models.Model):
    """Up to 3 images per Product"""
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='images', null=True)
    slot = models.IntegerField(help_text="1, 2, or 3")
    image = models.ImageField(upload_to=product_image_path)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['product', 'slot']]
        ordering = ['slot']

    def __str__(self):
        return f"{self.product.description} - Image {self.slot}"




# =============================================================================
# INVENTORY MODULE MODELS
# =============================================================================

class ItemGroup(TenantModel):
    """Item groups for organizing inventory items (e.g. Oysters, Tuna, Clams)"""
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'inventory_item_group'
        unique_together = [['tenant', 'name']]
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Product(TenantModel):
    """Product catalog — single source of truth for all products"""
    product_id = models.CharField(max_length=100, blank=True)
    item_number = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=255, blank=True)
    unit_type = models.CharField(max_length=50, blank=True)
    pack_size = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    default_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    sort_order = models.IntegerField(default=0)
    origin = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    buyer = models.CharField(max_length=100, blank=True)
    raw_cost = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    yield_pct = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    labor_pack_cost = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    pre_order_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # BlueTrace fields
    item_group = models.ForeignKey(ItemGroup, on_delete=models.SET_NULL, null=True, blank=True)
    item_name = models.CharField(max_length=255, blank=True, help_text="Auto-generated item name")
    qb_item_name = models.CharField(max_length=255, blank=True, help_text="QuickBooks item name")
    friendly_name = models.CharField(max_length=255, blank=True)
    size_cull = models.CharField(max_length=100, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    tasting_notes = models.TextField(blank=True)
    quantity_description = models.CharField(max_length=100, blank=True, help_text="e.g. Bag, Box, Case")
    country_of_origin = models.CharField(max_length=100, blank=True)
    brand = models.CharField(max_length=255, blank=True)
    inventory_unit_of_measure = models.CharField(max_length=50, blank=True, help_text="e.g. Lbs, Each, Bags")
    list_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Additional BlueTrace detail fields
    habitat_production_method = models.CharField(max_length=100, blank=True, help_text="e.g. Wild, Farm Raised, Aquaculture")
    species = models.CharField(max_length=100, blank=True, help_text="e.g. Eastern Oyster, Atlantic Salmon")
    department = models.CharField(max_length=100, blank=True, help_text="e.g. US Oysters, Fin Fish")
    upc = models.CharField(max_length=100, blank=True, help_text="Universal Product Code")
    selling_unit_of_measure = models.CharField(max_length=50, blank=True, help_text="e.g. Each, Lbs")
    selling_weight = models.CharField(max_length=50, blank=True)
    selling_volume = models.CharField(max_length=50, blank=True)
    selling_piece_count = models.CharField(max_length=50, blank=True)
    inventory_conversion = models.CharField(max_length=100, blank=True, help_text="e.g. 100 Each = 1 Bag")
    buying_unit_of_measure = models.CharField(max_length=50, blank=True, help_text="e.g. Bag, Case")
    buying_weight = models.CharField(max_length=50, blank=True)
    buying_volume = models.CharField(max_length=50, blank=True)
    buying_piece_count = models.CharField(max_length=50, blank=True)
    profit_margin_target = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Target profit margin %")

    class Meta:
        db_table = 'inventory_product'
        ordering = ['sort_order', 'description']

    def __str__(self):
        return self.description or f"{self.item_number} - {self.product_id}"

    def generate_item_name(self):
        """Auto-generate item name from component fields like BlueTrace"""
        parts = []
        if self.item_group:
            parts.append(self.item_group.name)
        if self.friendly_name:
            parts.append(self.friendly_name)
        elif self.qb_item_name:
            parts.append(self.qb_item_name)
        if self.origin:
            parts.append(self.origin)
        if self.size_cull:
            parts.append(self.size_cull)
        if self.quantity_description:
            parts.append(self.quantity_description)
        return ' · '.join(parts) if parts else self.description



class Inventory(TenantModel):
    """Inventory records"""

    productid = models.CharField(max_length=100, null=True, blank=True)
    desc = models.CharField(max_length=255, blank=True)
    vendorid = models.CharField(max_length=100, blank=True)
    receivedate = models.CharField(max_length=50, blank=True)
    vendorlot = models.CharField(max_length=100, blank=True)
    actualcost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unittype = models.CharField(max_length=50, blank=True)
    unitsonhand = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unitsavailable = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unitsallocated = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unitsin = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unitsout = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unitsstored = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    weightin = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    weightout = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    billedweight = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    availableweight = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    casesavailable = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    casesonhand = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    pendingunits = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    age = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    origin = models.CharField(max_length=100, blank=True)
    shelflife = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    critical = models.CharField(max_length=100, blank=True)
    packdate = models.CharField(max_length=50, blank=True)
    poid = models.CharField(max_length=100, blank=True)
    podid = models.CharField(max_length=100, blank=True)
    category = models.IntegerField(null=True, blank=True)
    storageid = models.IntegerField(null=True, blank=True)
    flagged = models.IntegerField(default=0)
    fixed = models.IntegerField(default=0)
    hidden = models.IntegerField(default=0)
    updatetime = models.CharField(max_length=50, blank=True)
    # Receiving fields
    location = models.CharField(max_length=100, blank=True, help_text="Storage location e.g. Cooler A")
    receive_time = models.CharField(max_length=20, blank=True, help_text="Time received e.g. 9:21 am")
    vendor_type = models.CharField(max_length=50, blank=True, help_text="e.g. Dealer, Harvester")

    class Meta:
        db_table = 'inventory_inventory'

    def __str__(self):
        return f"{self.productid} - {self.desc}"


# =============================================================================
# SALES ORDER MODULE MODELS
# =============================================================================

class SalesOrder(TenantModel):
    """Sales orders to customers."""
    ORDER_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('needs_review', 'Needs Review'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ]
    PACKED_STATUS_CHOICES = [
        ('not_packed', 'Not Packed'),
        ('packed', 'Packed'),
        ('need_to_send', 'Need To Send'),
    ]

    order_number = models.CharField(max_length=100)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    customer_name = models.CharField(max_length=255, blank=True)
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='draft')
    packed_status = models.CharField(max_length=20, choices=PACKED_STATUS_CHOICES, default='not_packed')
    qb_invoice_number = models.CharField(max_length=100, blank=True, help_text="QuickBooks Invoice #")
    sales_rep = models.CharField(max_length=100, blank=True)
    po_number = models.CharField(max_length=100, blank=True, help_text="Customer PO number")
    air_bill_number = models.CharField(max_length=100, blank=True)
    order_date = models.DateField(null=True, blank=True)
    pack_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    ship_date = models.DateField(null=True, blank=True)
    shipper = models.CharField(max_length=255, blank=True)
    shipping_route = models.CharField(max_length=100, blank=True)
    order_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Weight in Lbs")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales_orders',
    )
    assigned_to = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='assigned_orders',
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='completed_orders',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sales_order'
        unique_together = [['tenant', 'order_number']]
        ordering = ['-order_date', '-created_at']

    def __str__(self):
        return f"SO-{self.order_number} ({self.customer_name})"


class SalesOrderItem(TenantModel):
    """Line items on a sales order."""
    ITEM_TYPE_CHOICES = [
        ('item', 'Item'),
        ('fee', 'Fee'),
    ]

    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES, default='item')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unit_type = models.CharField(max_length=50, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    margin = models.CharField(max_length=50, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'sales_order_item'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.description} x {self.quantity}"


# =============================================================================
# PURCHASE ORDER MODULE MODELS
# =============================================================================

class PurchaseOrder(TenantModel):
    """Purchase orders placed with vendors."""
    ORDER_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ]
    RECEIVE_STATUS_CHOICES = [
        ('not_received', 'Not Received'),
        ('partial', 'Partial'),
        ('received', 'Received'),
    ]

    po_number = models.CharField(max_length=100)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    vendor_name = models.CharField(max_length=255, blank=True)
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='draft')
    receive_status = models.CharField(max_length=20, choices=RECEIVE_STATUS_CHOICES, default='not_received')
    qb_po_number = models.CharField(max_length=100, blank=True, help_text="QuickBooks PO #")
    buyer = models.CharField(max_length=100, blank=True)
    vendor_invoice_number = models.CharField(max_length=100, blank=True)
    order_date = models.DateField(null=True, blank=True)
    expected_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='purchase_orders',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'purchasing_order'
        unique_together = [['tenant', 'po_number']]
        ordering = ['-order_date', '-created_at']

    def __str__(self):
        return f"PO-{self.po_number} ({self.vendor_name})"

    @property
    def total(self):
        return sum(item.amount or 0 for item in self.items.all())


class PurchaseOrderItem(TenantModel):
    """Line items on a purchase order."""
    ITEM_TYPE_CHOICES = [
        ('item', 'Item'),
        ('fee', 'Fee'),
    ]

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES, default='item')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unit_type = models.CharField(max_length=50, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'purchasing_order_item'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.description} x {self.quantity}"


# =============================================================================
# FISH PROCESSING MODULE MODELS
# =============================================================================

class ProcessBatch(TenantModel):
    """A processing batch that transforms source lots into output lots."""
    PROCESS_TYPES = [
        ('fish_cutting', 'Fish Cutting'),
        ('commingle', 'Commingle'),
        ('renaming', 'Renaming'),
        ('freeze', 'Freeze'),
        ('lot_breaking', 'Bag or Lot Breaking'),
        ('shucking', 'Shucking'),
        ('wet_store', 'Wet Store'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    batch_number = models.CharField(max_length=100, unique=True)
    process_type = models.CharField(max_length=30, choices=PROCESS_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='process_batches',
    )

    class Meta:
        db_table = 'processing_batch'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.batch_number} ({self.get_process_type_display()})"


class ProcessBatchSource(TenantModel):
    """A source lot/inventory record used as input for a process batch."""
    batch = models.ForeignKey(ProcessBatch, on_delete=models.CASCADE, related_name='sources')
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    unit_type = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = 'processing_batch_source'

    def __str__(self):
        return f"{self.batch.batch_number} <- {self.inventory}"


class ProcessBatchOutput(TenantModel):
    """Output lot(s) produced by a process batch."""
    batch = models.ForeignKey(ProcessBatch, on_delete=models.CASCADE, related_name='outputs')
    inventory = models.ForeignKey(Inventory, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    unit_type = models.CharField(max_length=50, blank=True)
    lot_id = models.CharField(max_length=100, blank=True)
    yield_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                                        help_text="Yield % for this output")

    class Meta:
        db_table = 'processing_batch_output'

    def __str__(self):
        return f"{self.batch.batch_number} -> {self.lot_id}"


# =============================================================================
# FISH MARKET MODULE MODELS
# =============================================================================


class FishOrder(TenantModel):
    """Customer order submitted through the public fish market page"""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Ready', 'Ready'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]

    # Customer info
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=50)
    customer_address = models.TextField()

    # Payment info (no raw card numbers stored — only safe metadata)
    payment_type = models.CharField(max_length=50, default='card')  # card, cash, check
    card_holder_name = models.CharField(max_length=255, blank=True)
    card_last_four = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=50, blank=True)
    card_expiry = models.CharField(max_length=7, blank=True)  # MM/YYYY
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)

    # Order items as JSON: [{id, name, price, quantity, subtotal}]
    items_json = models.JSONField(default=list)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} - {self.customer_name}"


# =============================================================================
# ACCOUNTS PAYABLE MODULE
# =============================================================================

class APExpense(TenantModel):
    """Accounts Payable — logged expenses for the ledger"""
    STATUS_CHOICES = [
        ('Unpaid', 'Unpaid'),
        ('Paid', 'Paid'),
        ('Overdue', 'Overdue'),
    ]

    vendor = models.CharField(max_length=255)
    description = models.CharField(max_length=500)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=100, blank=True)
    due_date = models.DateField(null=True, blank=True)
    paid_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Unpaid')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.vendor} — ${self.amount}"


# =============================================================================
# ACCOUNTS RECEIVABLE MODULE
# =============================================================================

class ARInvoice(TenantModel):
    """Accounts Receivable — invoices owed to the business"""
    STATUS_CHOICES = [
        ('Unpaid', 'Unpaid'),
        ('Paid', 'Paid'),
        ('Overdue', 'Overdue'),
    ]

    customer = models.CharField(max_length=255)
    description = models.CharField(max_length=500)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    paid_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Unpaid')
    payment_type = models.CharField(max_length=100, blank=True)
    payment_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-invoice_date', '-created_at']

    def __str__(self):
        return f"{self.customer} — ${self.amount}"