from django.db import models
import uuid
from central.models import Product, Warehouse

from django.contrib.auth import get_user_model
from django.conf import settings
from apps.purchasing.utils import generate_company_year_number

user = get_user_model()


class Supplier(models.Model):
    """The master record for every vendor we buy from. It includes contact information, payment terms, and other details about the supplier."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    address = models.TextField()
    payment_terms = models.CharField(max_length=255)
    currency = models.CharField(max_length=10)
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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pr_number = models.CharField(max_length=20, unique=True, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="purchase_requisitions",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=50, default="Pending")
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
        Supplier, on_delete=models.CASCADE, related_name="purchase_orders"
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

    order_date = models.DateField(auto_now_add=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=10)
    description = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=50, choices=po_status_choices, default="Draft")
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
    """Line items for a purchase order, detailing the specific products or services being ordered, along with quantities, agreed prices, and any relevant notes."""

    unit_of_measure_choices = Product.UNIT_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="purchase_order_line_items",
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = models.CharField(max_length=50, choices=unit_of_measure_choices)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} {self.unit_of_measure} at {self.unit_price} each"


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
    invoice_date = models.DateField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=50, choices=invoice_status_choices, default="Draft"
    )
    description = models.TextField(blank=True)
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
