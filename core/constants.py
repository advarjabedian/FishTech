"""
Centralized constants for the FishTech application.
Import these in models.py and views instead of defining inline choices.
"""

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


# =============================================================================
# INVENTORY ADJUSTMENTS
# =============================================================================

INVENTORY_ADJUSTMENT_TYPE_CHOICES = [
    ('increase', 'Increase'),
    ('decrease', 'Decrease'),
    ('set_count', 'Set Count'),
]

INVENTORY_ADJUSTMENT_REASON_CHOICES = [
    ('count_correction', 'Count Correction'),
    ('damage', 'Damage'),
    ('shrinkage', 'Shrinkage'),
    ('spoilage', 'Spoilage'),
    ('waste', 'Waste'),
    ('sample', 'Sample / QA Pull'),
    ('return', 'Return / Restock'),
    ('other', 'Other'),
]


# =============================================================================
# PROCESSING WASTE / BYPRODUCT
# =============================================================================

PROCESS_WASTE_TYPE_CHOICES = [
    ('waste', 'Waste'),
    ('byproduct', 'Byproduct'),
]

PROCESS_WASTE_CATEGORY_CHOICES = [
    ('trim', 'Trim'),
    ('shell', 'Shell'),
    ('spoilage', 'Spoilage'),
    ('damage', 'Damage'),
    ('sample', 'QA Sample'),
    ('rework', 'Rework'),
    ('donation', 'Donation'),
    ('other', 'Other'),
]


# =============================================================================
# RECEIVING QUALITY
# =============================================================================

RECEIVING_QUALITY_STATUS_CHOICES = [
    ('pass', 'Pass'),
    ('hold', 'Hold'),
    ('reject', 'Reject'),
]
