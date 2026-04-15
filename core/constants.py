"""
Centralized constants for the FishTech application.
Import these in models.py and views instead of defining inline choices.
"""

# =============================================================================
# SUBSCRIPTION & TENANT
# =============================================================================

SUBSCRIPTION_STATUS_CHOICES = [
    ('trialing', 'Trial'),
    ('active', 'Active'),
    ('past_due', 'Past Due'),
    ('canceled', 'Canceled'),
    ('unpaid', 'Unpaid'),
]

LEAD_STAGE_CHOICES = [
    ('prospect', 'Prospect'),
    ('contacted', 'Contacted'),
    ('demo', 'Demo Scheduled'),
    ('proposal', 'Proposal Sent'),
    ('negotiation', 'Negotiation'),
    ('won', 'Won'),
    ('lost', 'Lost'),
]

TENANT_DOCUMENT_TYPES = [
    ('subscription_agreement', 'Subscription Agreement'),
    ('privacy_policy', 'Privacy Policy'),
    ('sla', 'Service Level Agreement'),
]


# =============================================================================
# HACCP & COMPLIANCE
# =============================================================================

HACCP_STATUS_CHOICES = [
    ('not_started', 'Not Started'),
    ('in_progress', 'In Progress'),
    ('completed', 'Completed'),
]

# HACCP document subtypes
HACCP_DOC_PRODUCT_DESCRIPTION = 'product_description'
HACCP_DOC_FLOW_CHART = 'flow_chart'
HACCP_DOC_HAZARD_ANALYSIS = 'hazard_analysis'
HACCP_DOC_CCP_SUMMARY = 'ccp_summary'

HACCP_DOCUMENT_TYPES = [
    HACCP_DOC_PRODUCT_DESCRIPTION,
    HACCP_DOC_FLOW_CHART,
    HACCP_DOC_HAZARD_ANALYSIS,
    HACCP_DOC_CCP_SUMMARY,
]

HACCP_DOCUMENT_TYPE_LABELS = {
    HACCP_DOC_PRODUCT_DESCRIPTION: 'Product Description',
    HACCP_DOC_FLOW_CHART: 'Flow Chart',
    HACCP_DOC_HAZARD_ANALYSIS: 'Hazard Analysis',
    HACCP_DOC_CCP_SUMMARY: 'CCP Summary',
}

CERTIFICATE_TYPE_CHOICES = [
    ('haccp_certificate', 'HACCP Certificate'),
    ('letter_of_guarantee', 'Letter of Guarantee'),
]


# =============================================================================
# OPERATIONS / INSPECTIONS
# =============================================================================

SHIFT_PRE_OP = 'Pre-Op'
SHIFT_MID_DAY = 'Mid-Day'
SHIFT_POST_OP = 'Post-Op'

SHIFT_CHOICES = [
    (SHIFT_PRE_OP, 'Pre-Op'),
    (SHIFT_MID_DAY, 'Mid-Day'),
    (SHIFT_POST_OP, 'Post-Op'),
]

SHIFT_NAMES = [SHIFT_PRE_OP, SHIFT_MID_DAY, SHIFT_POST_OP]


# =============================================================================
# DOCUMENTS & CONTACTS
# =============================================================================

CONTACT_TYPE_CHOICES = [
    ('customer', 'Customer'),
    ('vendor', 'Vendor'),
    ('tenant', 'Tenant'),
]

DOCUMENT_FILE_TYPE_CHOICES = [
    ('so', 'Sales Order'),
    ('po', 'Purchase Order'),
    ('pod', 'POD'),
    ('customer', 'Customer'),
    ('vendor', 'Vendor'),
    ('receipt', 'Receipt'),
]

MESSAGE_SOURCE_CHOICES = [
    ('email', 'Email'),
    ('voicemail', 'Voicemail'),
    ('sms', 'SMS/Text'),
]


# =============================================================================
# ORDERS (SALES & PURCHASE)
# =============================================================================

SALES_ORDER_STATUS_CHOICES = [
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

PURCHASE_ORDER_STATUS_CHOICES = [
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

ORDER_ITEM_TYPE_CHOICES = [
    ('item', 'Item'),
    ('fee', 'Fee'),
]


# =============================================================================
# PROCESSING
# =============================================================================

PROCESS_TYPE_CHOICES = [
    ('fish_cutting', 'Fish Cutting'),
    ('commingle', 'Commingle'),
    ('renaming', 'Renaming'),
    ('freeze', 'Freeze'),
    ('lot_breaking', 'Bag or Lot Breaking'),
    ('shucking', 'Shucking'),
    ('wet_store', 'Wet Store'),
]

PROCESS_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('in_progress', 'In Progress'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]


# =============================================================================
# FISH MARKET (RETAIL)
# =============================================================================

FISH_ORDER_STATUS_CHOICES = [
    ('Pending', 'Pending'),
    ('Confirmed', 'Confirmed'),
    ('Ready', 'Ready'),
    ('Delivered', 'Delivered'),
    ('Cancelled', 'Cancelled'),
]


# =============================================================================
# FINANCE
# =============================================================================

FINANCIAL_STATUS_CHOICES = [
    ('Unpaid', 'Unpaid'),
    ('Paid', 'Paid'),
    ('Overdue', 'Overdue'),
]
