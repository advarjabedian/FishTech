from django.db import models
from django.contrib.auth.models import User as DjangoUser
from threading import local
from django.conf import settings
import uuid
from . import constants as C

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
    created_at = models.DateField(null=True, blank=True)

    # Facility info (formerly on Company)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    zipcode = models.CharField(max_length=10, blank=True)
    logo = models.TextField(blank=True)

    def __str__(self):
        return self.name

class TenantUser(models.Model):
    """Links Django users to tenants"""
    user = models.OneToOneField(DjangoUser, on_delete=models.CASCADE)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    is_admin = models.BooleanField(default=False)
    signature = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.tenant.name}"


class TenantBillingProfile(models.Model):
    """Stores Stripe billing linkage and the latest synced billing snapshot for a tenant."""
    BILLING_STATUS_CHOICES = [
        ("unknown", "Unknown"),
        ("incomplete", "Incomplete"),
        ("incomplete_expired", "Incomplete Expired"),
        ("trialing", "Trialing"),
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("canceled", "Canceled"),
        ("unpaid", "Unpaid"),
        ("paused", "Paused"),
    ]

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="billing_profile")
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    stripe_price_id = models.CharField(max_length=255, blank=True)
    subscription_status = models.CharField(max_length=32, choices=BILLING_STATUS_CHOICES, default="unknown")
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    latest_invoice_id = models.CharField(max_length=255, blank=True)
    latest_invoice_status = models.CharField(max_length=64, blank=True)
    latest_invoice_amount_due = models.IntegerField(null=True, blank=True)
    latest_invoice_amount_paid = models.IntegerField(null=True, blank=True)
    latest_invoice_currency = models.CharField(max_length=16, blank=True)
    latest_invoice_created_at = models.DateTimeField(null=True, blank=True)
    customer_email = models.EmailField(blank=True)
    last_checkout_session_id = models.CharField(max_length=255, blank=True)
    last_checkout_completed_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tenant__name"]

    def __str__(self):
        return f"Billing profile for {self.tenant.name}"


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
    CONTACT_TYPE_CHOICES = C.CONTACT_TYPE_CHOICES
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
    DOCUMENT_TYPE_CHOICES = C.DOCUMENT_FILE_TYPE_CHOICES
    
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
        """Keep product naming clean and let units or pack live in dedicated fields."""
        if self.description:
            return self.description
        if self.friendly_name:
            return self.friendly_name
        if self.qb_item_name:
            return self.qb_item_name
        return self.product_id or ""



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
    purchase_order = models.ForeignKey('PurchaseOrder', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='received_lots', help_text="Linked purchase order")
    po_item = models.ForeignKey('PurchaseOrderItem', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='received_lots', help_text="Specific PO line item received against")
    podid = models.CharField(max_length=100, blank=True)
    # Weight variance fields (populated when receiving against a PO)
    expected_weight = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True,
                                         help_text="Expected weight from PO line item")
    weight_variance = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True,
                                          help_text="Received weight minus expected weight (negative = short)")
    quantity_variance = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True,
                                           help_text="Received qty minus expected qty")
    variance_flagged = models.BooleanField(default=False,
                                           help_text="True if variance exceeds threshold")
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


class InventoryAdjustment(TenantModel):
    """Audit log for inventory quantity adjustments."""
    ADJUSTMENT_TYPE_CHOICES = C.INVENTORY_ADJUSTMENT_TYPE_CHOICES
    REASON_CHOICES = C.INVENTORY_ADJUSTMENT_REASON_CHOICES

    inventory = models.ForeignKey('Inventory', on_delete=models.CASCADE, related_name='adjustments')
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True)
    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPE_CHOICES)
    reason_code = models.CharField(max_length=30, choices=REASON_CHOICES)
    quantity_before = models.DecimalField(max_digits=12, decimal_places=4)
    quantity_delta = models.DecimalField(max_digits=12, decimal_places=4)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=4)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='inventory_adjustments',
    )
    created_by_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'inventory_adjustment'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.inventory_id} {self.adjustment_type} {self.quantity_delta}"


class ReceivingQualityCheck(TenantModel):
    """Freshness and receiving quality checklist for a received lot."""
    STATUS_CHOICES = C.RECEIVING_QUALITY_STATUS_CHOICES

    inventory = models.OneToOneField(Inventory, on_delete=models.CASCADE, related_name='quality_check')
    freshness_score = models.PositiveSmallIntegerField(default=0)
    appearance_ok = models.BooleanField(default=False)
    odor_ok = models.BooleanField(default=False)
    texture_ok = models.BooleanField(default=False)
    packaging_ok = models.BooleanField(default=False)
    temp_ok = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pass')
    notes = models.TextField(blank=True)
    checked_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='receiving_quality_checks',
    )
    checked_by_name = models.CharField(max_length=100, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'receiving_quality_check'

    def __str__(self):
        return f"{self.inventory_id} quality {self.status}"


# =============================================================================
# SALES ORDER MODULE MODELS
# =============================================================================

class SalesOrder(TenantModel):
    """Sales orders to customers."""
    ORDER_STATUS_CHOICES = C.SALES_ORDER_STATUS_CHOICES
    PACKED_STATUS_CHOICES = C.PACKED_STATUS_CHOICES

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

    # Delivery / Proof of Delivery
    DELIVERY_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('confirmed', 'Confirmed'),
        ('exception', 'Exception'),
    ]
    delivery_status = models.CharField(max_length=20, choices=DELIVERY_STATUS_CHOICES, default='pending')
    actual_delivery_date = models.DateTimeField(null=True, blank=True)
    driver_name = models.CharField(max_length=100, blank=True)
    delivery_notes = models.TextField(blank=True)
    recipient_name = models.CharField(max_length=100, blank=True, help_text="Person who received the delivery")
    pod_signature = models.TextField(blank=True, help_text="Base64 signature from recipient")
    pod_photo = models.CharField(max_length=500, blank=True, help_text="Path to delivery photo")
    delivery_temperature = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                                               help_text="Product temperature at delivery (°F)")

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
    ITEM_TYPE_CHOICES = C.ORDER_ITEM_TYPE_CHOICES

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
    process_type = models.CharField(max_length=30, choices=C.PROCESS_TYPE_CHOICES, blank=True)
    process_source_lot_ids = models.TextField(blank=True, help_text="Comma-separated inventory IDs selected as process sources")
    process_batch = models.ForeignKey('ProcessBatch', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_items')
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'sales_order_item'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.description} x {self.quantity}"


class SalesOrderAllocation(TenantModel):
    """Inventory lot allocations reserved against sales order items."""
    sales_order_item = models.ForeignKey(SalesOrderItem, on_delete=models.CASCADE, related_name='allocations')
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='sales_allocations')
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    unit_type = models.CharField(max_length=50, blank=True)
    allocated_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales_order_allocations',
    )
    allocated_by_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sales_order_allocation'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f"SO item {self.sales_order_item_id} <- inventory {self.inventory_id}"


# =============================================================================
# PURCHASE ORDER MODULE MODELS
# =============================================================================

class PurchaseOrder(TenantModel):
    """Purchase orders placed with vendors."""
    ORDER_STATUS_CHOICES = C.PURCHASE_ORDER_STATUS_CHOICES
    RECEIVE_STATUS_CHOICES = C.RECEIVE_STATUS_CHOICES

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
    ITEM_TYPE_CHOICES = C.ORDER_ITEM_TYPE_CHOICES

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

    # Receiving tracking
    received_quantity = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                           help_text="Total quantity received against this line")
    received_weight = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True,
                                         help_text="Total weight received against this line")

    class Meta:
        db_table = 'purchasing_order_item'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.description} x {self.quantity}"

    @property
    def remaining_quantity(self):
        return (self.quantity or 0) - (self.received_quantity or 0)

    @property
    def is_fully_received(self):
        return self.quantity and self.received_quantity >= self.quantity


# =============================================================================
# FISH PROCESSING MODULE MODELS
# =============================================================================

class ProcessBatch(TenantModel):
    """A processing batch that transforms source lots into output lots."""
    PROCESS_TYPES = C.PROCESS_TYPE_CHOICES
    STATUS_CHOICES = C.PROCESS_STATUS_CHOICES

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

    # Yield tracking (calculated on batch completion)
    total_input_weight = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True,
                                             help_text="Sum of all source lot quantities")
    total_output_weight = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True,
                                              help_text="Sum of all output quantities")
    actual_yield_pct = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                                           help_text="Actual yield: output/input * 100")
    expected_yield_pct = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                                             help_text="Expected yield from product catalog")
    yield_variance_pct = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                                             help_text="Actual minus expected yield")
    yield_flagged = models.BooleanField(default=False,
                                        help_text="True if yield is significantly below expected")

    class Meta:
        db_table = 'processing_batch'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.batch_number} ({self.get_process_type_display()})"

    def calculate_yield(self):
        """Calculate yield from sources and outputs. Call after outputs are finalized."""
        from django.db.models import Sum
        input_total = self.sources.aggregate(total=Sum('quantity'))['total'] or 0
        output_total = self.outputs.aggregate(total=Sum('quantity'))['total'] or 0

        self.total_input_weight = input_total
        self.total_output_weight = output_total
        self.actual_yield_pct = (output_total / input_total * 100) if input_total else None

        # Get expected yield from first output's product
        first_output = self.outputs.select_related('product').first()
        if first_output and first_output.product and first_output.product.yield_pct:
            self.expected_yield_pct = first_output.product.yield_pct * 100  # stored as 0.45 -> 45%
            if self.actual_yield_pct is not None:
                self.yield_variance_pct = self.actual_yield_pct - self.expected_yield_pct
                self.yield_flagged = self.yield_variance_pct < -5  # Flag if >5% below expected


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


class ProcessBatchWaste(TenantModel):
    """Waste and byproduct entries recorded during processing."""
    ENTRY_TYPE_CHOICES = C.PROCESS_WASTE_TYPE_CHOICES
    CATEGORY_CHOICES = C.PROCESS_WASTE_CATEGORY_CHOICES

    batch = models.ForeignKey(ProcessBatch, on_delete=models.CASCADE, related_name='waste_entries')
    source_inventory = models.ForeignKey(Inventory, on_delete=models.SET_NULL, null=True, blank=True)
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    unit_type = models.CharField(max_length=50, blank=True)
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='process_batch_waste_entries',
    )
    created_by_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'processing_batch_waste'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.batch.batch_number} {self.entry_type} {self.quantity}"


# =============================================================================
# CCP MONITORING LOG
# =============================================================================

class CCPLog(TenantModel):
    """Timestamped CCP (Critical Control Point) monitoring reading.
    Individual readings tied to lots/batches for full traceability.
    """
    CCP_TYPE_CHOICES = [
        ('receiving_temp', 'Receiving Temperature'),
        ('processing_temp', 'Processing Room Temperature'),
        ('product_temp', 'Internal Product Temperature'),
        ('cooler_temp', 'Cooler/Storage Temperature'),
        ('sanitation', 'Sanitation Check'),
        ('other', 'Other'),
    ]

    RESULT_CHOICES = [
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('corrective', 'Corrective Action Taken'),
    ]

    ccp_type = models.CharField(max_length=30, choices=CCP_TYPE_CHOICES)
    reading_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                        help_text="Numeric reading (e.g. temperature in °F)")
    unit = models.CharField(max_length=10, default='°F', blank=True)
    critical_limit_min = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                             help_text="Lower acceptable limit")
    critical_limit_max = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                             help_text="Upper acceptable limit (e.g. 40°F for receiving)")
    result = models.CharField(max_length=15, choices=RESULT_CHOICES, default='pass')
    out_of_range = models.BooleanField(default=False, help_text="Auto-set if reading exceeds limits")

    # What was being monitored
    location = models.CharField(max_length=100, blank=True, help_text="e.g. Dock, Processing Room, Cooler A")
    description = models.CharField(max_length=255, blank=True, help_text="What was checked")

    # Traceability links
    inventory = models.ForeignKey('Inventory', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='ccp_logs', help_text="Lot this reading applies to")
    process_batch = models.ForeignKey('ProcessBatch', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='ccp_logs', help_text="Processing batch this reading applies to")

    # Corrective action (required when out of range)
    corrective_action = models.TextField(blank=True)
    corrective_action_by = models.CharField(max_length=100, blank=True)

    # Who and when
    recorded_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    recorded_by_name = models.CharField(max_length=100, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ccp_monitoring_log'
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.get_ccp_type_display()} — {self.reading_value}{self.unit} ({self.result})"

    def save(self, *args, **kwargs):
        # Auto-flag if reading is out of range
        if self.reading_value is not None:
            if self.critical_limit_max and self.reading_value > self.critical_limit_max:
                self.out_of_range = True
            elif self.critical_limit_min and self.reading_value < self.critical_limit_min:
                self.out_of_range = True
            else:
                self.out_of_range = False
            if self.out_of_range and self.result == 'pass':
                self.result = 'fail'
        super().save(*args, **kwargs)


# =============================================================================
# FISH MARKET MODULE MODELS
# =============================================================================


class FishOrder(TenantModel):
    """Customer order submitted through the public fish market page"""
    STATUS_CHOICES = C.FISH_ORDER_STATUS_CHOICES

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
    STATUS_CHOICES = C.FINANCIAL_STATUS_CHOICES

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
    STATUS_CHOICES = C.FINANCIAL_STATUS_CHOICES

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
