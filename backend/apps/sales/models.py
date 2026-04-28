import uuid
from django.conf import settings
from django.db import models
from central.models import Product, Warehouse
from apps.inventory.models import Batch
from apps.sales.utils import generate_reference_number


class Customer(models.Model):
    CUSTOMER_TYPE_CHOICES = [
        ("retail", "Retail"),
        ("business", "Business"),
    ]
    PAYMENT_TERMS_CHOICES = [
        ("cash", "Cash"),
        ("net_30", "Net 30"),
        ("net_60", "Net 60"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS_CHOICES, default="cash")
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    tax_number = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        indexes = [
            models.Index(fields=["customer_type"], name="customer_type_idx"),
            models.Index(fields=["is_active"], name="customer_is_active_idx"),
        ]

    def __str__(self):
        return self.name


class CustomerProduct(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="product_agreements")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="customer_agreements")
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    min_order_quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Customer Product"
        verbose_name_plural = "Customer Products"
        indexes = [
            models.Index(fields=["customer", "product"], name="custprod_customer_product_idx"),
            models.Index(fields=["is_active", "valid_from"], name="custprod_active_valid_from_idx"),
        ]

    def __str__(self):
        return f"{self.customer} - {self.product}"


class SalesOrder(models.Model):
    ORDER_TYPE_CHOICES = [("pos", "POS"), ("b2b", "B2B")]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("picking", "Picking"),
        ("dispatched", "Dispatched"),
        ("invoiced", "Invoiced"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales_orders")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="sales_orders")
    order_type = models.CharField(max_length=10, choices=ORDER_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    order_date = models.DateTimeField()
    expected_delivery_date = models.DateField(null=True, blank=True)
    delivery_address = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales_orders_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sales Order"
        verbose_name_plural = "Sales Orders"
        indexes = [
            models.Index(fields=["status", "order_type"], name="so_status_order_type_idx"),
            models.Index(fields=["customer", "status"], name="so_customer_status_idx"),
            models.Index(fields=["created_at"], name="so_created_at_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = generate_reference_number("SO", SalesOrder, "order_number")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number


class SalesOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="sales_order_lines")
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    quantity_dispatched = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cost_per_unit = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    cogs_total = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Sales Order Line"
        verbose_name_plural = "Sales Order Lines"
        indexes = [
            models.Index(fields=["sales_order", "product"], name="sol_sales_order_product_idx"),
        ]

    def __str__(self):
        return f"{self.sales_order} - {self.product}"


class Delivery(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_transit", "In Transit"),
        ("delivered", "Delivered"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name="deliveries")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="deliveries")
    delivery_number = models.CharField(max_length=20, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    dispatched_at = models.DateTimeField()
    delivered_at = models.DateTimeField(null=True, blank=True)
    driver_name = models.CharField(max_length=255, null=True, blank=True)
    vehicle = models.CharField(max_length=100, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="deliveries_created"
    )

    class Meta:
        verbose_name = "Delivery"
        verbose_name_plural = "Deliveries"
        indexes = [
            models.Index(fields=["sales_order", "status"], name="delivery_so_status_idx"),
            models.Index(fields=["status"], name="delivery_status_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.delivery_number:
            self.delivery_number = generate_reference_number("DEL", Delivery, "delivery_number")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.delivery_number


class DeliveryLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="lines")
    sales_order_line = models.ForeignKey(SalesOrderLine, on_delete=models.PROTECT, related_name="delivery_lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="delivery_lines")
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="delivery_lines")
    quantity_delivered = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Delivery Line"
        verbose_name_plural = "Delivery Lines"
        indexes = [
            models.Index(fields=["delivery", "sales_order_line"], name="deliveryline_delivery_sol_idx"),
        ]

    def __str__(self):
        return f"{self.delivery} - {self.product} ({self.quantity_delivered})"


class Invoice(models.Model):
    INVOICE_TYPE_CHOICES = [("receipt", "Receipt"), ("tax_invoice", "Tax Invoice")]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("issued", "Issued"),
        ("partially_paid", "Partially Paid"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sales_order = models.OneToOneField(SalesOrder, on_delete=models.PROTECT, related_name="invoice")
    invoice_number = models.CharField(max_length=20, unique=True, editable=False)
    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPE_CHOICES)
    issued_date = models.DateField()
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="invoices_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
        indexes = [
            models.Index(fields=["status"], name="invoice_status_idx"),
            models.Index(fields=["due_date", "status"], name="invoice_due_date_status_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = generate_reference_number("INV", Invoice, "invoice_number")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.invoice_number


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
        ("mobile_money", "Mobile Money"),
        ("cheque", "Cheque"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_date = models.DateTimeField()
    reference = models.CharField(max_length=255, null=True, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments_received"
    )
    notes = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        indexes = [
            models.Index(fields=["invoice", "payment_date"], name="payment_invoice_date_idx"),
            models.Index(fields=["customer"], name="payment_customer_idx"),
        ]

    def __str__(self):
        return f"Payment {self.amount} for {self.invoice}"
