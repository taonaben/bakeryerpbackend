from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
import uuid
from central.models import Company, Product, Warehouse

from django.contrib.auth import get_user_model
from django.conf import settings
from apps.purchasing.utils import generate_company_year_number

user = get_user_model()

VALID_DELIVERY_DAYS = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}


def validate_delivery_days(value):
    if not isinstance(value, list):
        raise ValidationError("delivery_days must be a list.")
    invalid = [v for v in value if v not in VALID_DELIVERY_DAYS]
    if invalid:
        raise ValidationError(
            f"Invalid delivery day(s): {invalid}. "
            f"Must be one of {sorted(VALID_DELIVERY_DAYS)}."
        )


class Supplier(models.Model):
    """The master record for every vendor we buy from. It includes contact information, payment terms, and other details about the supplier."""

    PAYMENT_TERMS_CHOICES = [
        ("NET_30", "Net 30"),
        ("NET_60", "Net 60"),
        ("COD", "Cash on Delivery"),
        ("EOM", "End of Month"),
        ("PREPAID", "Prepaid"),
        ("IMMEDIATE", "Immediate"),
    ]

    SUPPLIER_TYPE_CHOICES = [
        ("MANUFACTURER", "Manufacturer"),
        ("DISTRIBUTOR", "Distributor"),
        ("AGENT", "Agent"),
        ("INDIVIDUAL", "Individual"),
    ]

    DELIVERY_METHOD_CHOICES = [
        ("OWN_TRANSPORT", "Own Transport"),
        ("COURIER", "Courier"),
        ("COLLECT", "Collect"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="suppliers"
    )

    # Identity & Compliance
    name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=100, blank=True)
    tax_number = models.CharField(max_length=100, blank=True)
    supplier_type = models.CharField(
        max_length=20, choices=SUPPLIER_TYPE_CHOICES, blank=True
    )

    # Contact & Location
    primary_email = models.EmailField()
    secondary_email = models.EmailField(blank=True)
    primary_phone = models.CharField(max_length=20)
    alternate_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)

    # Financial
    payment_terms = models.CharField(
        max_length=20, choices=PAYMENT_TERMS_CHOICES, blank=True
    )
    currency = models.CharField(max_length=10)
    credit_limit = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    bank_name = models.CharField(max_length=200, blank=True)
    bank_branch = models.CharField(max_length=200, blank=True)
    bank_account_number = models.CharField(max_length=100, blank=True)
    can_supply_on_credit = models.BooleanField(default=False)

    # Logistics
    default_lead_time_days = models.IntegerField(null=True, blank=True)
    minimum_order_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    delivery_days = models.JSONField(
        default=list, blank=True, validators=[validate_delivery_days]
    )
    delivery_method = models.CharField(
        max_length=20, choices=DELIVERY_METHOD_CHOICES, blank=True
    )
    delivery_radius_km = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    warehouses_served = models.ManyToManyField(
        Warehouse, blank=True, related_name="served_suppliers"
    )

    # Performance & Internal
    rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    internal_notes = models.TextField(blank=True)
    on_hold = models.BooleanField(default=False)
    on_hold_reason = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class SupplierProduct(models.Model):
    """This model links suppliers to the products they provide, including details like price and lead time."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="supplier_products"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="supplier_products"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    lead_time_days = models.IntegerField()
    is_preferred = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            "supplier",
            "product",
        )  # Ensure a supplier can only have one entry per product

    def __str__(self):
        return f"{self.supplier.name} - {self.product.name}"


class PurchaseRequisition(models.Model):
    """A purchase requisition is an internal document that employees use to request the purchase of goods or services. It includes details about the requested items, quantities, and justification for the purchase."""

    pr_status_choices = [
        ("Draft", "Draft"),
        ("Submitted", "Submitted"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("Converted", "Converted"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pr_number = models.CharField(max_length=20, unique=True, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="purchase_requisitions",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="purchase_requisitions",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=50, choices=pr_status_choices, default="Draft")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_purchase_requisitions",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_purchase_requisitions",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_purchase_requisitions",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_pr_number(self):
        if not self.requested_by or not self.requested_by.company:
            raise ValueError("Purchase requisition requires a user with a company.")

        return generate_company_year_number(
            model_cls=PurchaseRequisition,
            prefix="PR",
            company=self.requested_by.company,
            number_field="pr_number",
            company_field="requested_by__company",
        )

    def save(self, *args, **kwargs):
        if not self.pr_number:
            self.pr_number = self.generate_pr_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.pr_number


class PurchaseRequisitionLineItem(models.Model):
    """Line items for a purchase requisition, detailing the specific products or services being requested, along with quantities and any relevant notes."""

    unit_of_measure_choices = Product.UNIT_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_requisition = models.ForeignKey(
        PurchaseRequisition,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="purchase_requisition_line_items",
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = models.CharField(max_length=50, choices=unit_of_measure_choices)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} {self.unit_of_measure}"


class PurchaseOrder(models.Model):
    """A purchase order is a formal document sent to a supplier to request the delivery of goods or services. It includes details about the items being ordered, quantities, agreed prices, and delivery instructions."""

    po_status_choices = [
        ("Draft", "Draft"),
        ("Approved", "Approved"),
        ("Submitted", "Submitted"),
        ("Partially Received", "Partially Received"),
        ("Received", "Received"),
        ("Rejected", "Rejected"),
        ("Cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po_number = models.CharField(max_length=20, unique=True, blank=True)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders",
        help_text="Optional primary/default supplier for this PO. Each line item carries its own supplier.",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )
    purchase_requisition = models.ForeignKey(
        PurchaseRequisition,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,  # Allow PO without PR for direct purchases
        related_name="purchase_orders",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_purchase_orders",
    )

    order_date = models.DateField(auto_now_add=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=10)
    description = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=50, choices=po_status_choices, default="Draft")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_purchase_orders",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_purchase_orders",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_purchase_orders",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_purchase_orders",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_po_number(self):
        if not self.warehouse or not self.warehouse.company:
            raise ValueError("Purchase order requires a warehouse with a company.")

        return generate_company_year_number(
            model_cls=PurchaseOrder,
            prefix="PO",
            company=self.warehouse.company,
            number_field="po_number",
            company_field="warehouse__company",
        )

    def save(self, *args, **kwargs):
        if not self.po_number:
            self.po_number = self.generate_po_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.po_number


class PurchaseOrderLineItem(models.Model):
    """Line items for a purchase order, detailing the specific products or services being ordered, along with quantities, agreed prices, and any relevant notes.

    Each line carries its own supplier so a single PO can consolidate items from
    multiple vendors.  ``quoted_price`` is the price on record in SupplierProduct
    (auto-filled by the frontend); ``unit_price`` is the price agreed on the day
    (editable, e.g. to reflect a discount).
    """

    unit_of_measure_choices = Product.UNIT_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_order_line_items",
        help_text="The supplier providing this specific line item.",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="purchase_order_line_items",
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = models.CharField(max_length=50, choices=unit_of_measure_choices)
    quoted_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Supplier's catalogue/quoted price (auto-filled from SupplierProduct).",
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Agreed price for this order (may differ from quoted price due to discounts, etc.).",
    )
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_received = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        supplier_name = self.supplier.name if self.supplier else "No supplier"
        return f"{self.product.name} - {self.quantity} {self.unit_of_measure} at {self.unit_price} each ({supplier_name})"


class GoodsReceipt(models.Model):
    """
    Records the receipt of goods from a supplier, including details about the items received, quantities, and any discrepancies between the purchase order and the actual delivery.
    This is the trigger for inventory updates and can also be used for quality control and supplier performance evaluation.
    """

    gr_choices = [
        ("Draft", "Draft"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gr_number = models.CharField(max_length=20, unique=True, blank=True)
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="goods_receipts",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts",
    )
    received_date = models.DateField(auto_now_add=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts",
    )
    status = models.CharField(max_length=50, choices=gr_choices, default="Draft")
    description = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def generate_gr_number(self):
        if not self.warehouse or not self.warehouse.company:
            raise ValueError("Goods receipt requires a warehouse with a company.")

        return generate_company_year_number(
            model_cls=GoodsReceipt,
            prefix="GR",
            company=self.warehouse.company,
            number_field="gr_number",
            company_field="warehouse__company",
        )

    def save(self, *args, **kwargs):
        if not self.gr_number:
            self.gr_number = self.generate_gr_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.gr_number


class GoodsReceiptLineItem(models.Model):
    """Line items for a goods receipt, detailing the specific products received, along with quantities and any discrepancies compared to the purchase order."""

    unit_of_measure_choices = Product.UNIT_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goods_receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    po_line_item = models.ForeignKey(
        PurchaseOrderLineItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipt_line_items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="goods_receipt_line_items",
    )
    quantity_received = models.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = models.CharField(max_length=50, choices=unit_of_measure_choices)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    supplier_batch_ref = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    manufacturing_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity_received} {self.unit_of_measure}"


class SupplierInvoice(models.Model):
    """Records the invoice sent by the supplier for the goods or services provided, including details about the amounts due, payment terms, and any discrepancies compared to the purchase order."""

    invoice_status_choices = [
        ("Draft", "Draft"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("Paid", "Paid"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=20, unique=True, blank=True)
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="supplier_invoices",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="supplier_invoices",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_invoices",
    )
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=50, choices=invoice_status_choices, default="Draft"
    )
    description = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_supplier_invoices",
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_supplier_invoices",
    )
    rejection_reason = models.TextField(blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paid_supplier_invoices",
    )
    payment_reference = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_invoice_number(self):
        if not self.warehouse or not self.warehouse.company:
            raise ValueError("Supplier invoice requires a warehouse with a company.")

        return generate_company_year_number(
            model_cls=SupplierInvoice,
            prefix="INV",
            company=self.warehouse.company if self.warehouse else None,
            number_field="invoice_number",
            company_field="warehouse__company",
        )

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_number


class SupplierInvoiceLineItem(models.Model):
    """Line items for a supplier invoice, detailing the specific products or services invoiced, along with amounts and any discrepancies compared to the purchase order."""

    unit_of_measure_choices = Product.UNIT_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier_invoice = models.ForeignKey(
        SupplierInvoice,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    gr_line_item = models.ForeignKey(
        GoodsReceiptLineItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_invoice_line_items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="supplier_invoice_line_items",
    )
    quantity_invoiced = models.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = models.CharField(max_length=50, choices=unit_of_measure_choices)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity_invoiced * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.quantity_invoiced} {self.unit_of_measure} at {self.unit_price} each"


class PurchasingConfig(models.Model):
    """Company-level configuration for purchasing tolerances and rules.
    One record per company."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField(
        "central.Company",
        on_delete=models.CASCADE,
        related_name="purchasing_config",
    )
    price_tolerance_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=2.00
    )
    qty_tolerance_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=2.00
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PurchasingConfig for {self.company.name}"


class SupplierContact(models.Model):
    """A contact person associated with a supplier. Multiple contacts can exist per supplier; one may be marked as primary."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="contacts"
    )
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.supplier.name})"


class SupplierDocument(models.Model):
    """Documents associated with a supplier (contracts, health certificates, tax clearance, etc.). The expiry_date field is critical for food-sector compliance tracking."""

    DOCUMENT_TYPE_CHOICES = [
        ("CONTRACT", "Contract"),
        ("HEALTH_CERT", "Health Certificate"),
        ("TAX_CLEARANCE", "Tax Clearance"),
        ("CERTIFICATION", "Certification"),
        ("OTHER", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
    name = models.CharField(max_length=255)
    file_url = models.CharField(max_length=500, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.supplier.name})"
