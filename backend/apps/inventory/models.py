from django.db import models
import uuid
from central.models import Product, Warehouse
from django.db.models import F
from apps.accounts.models import User


class Stock(models.Model):
    """Represents current inventory levels of a product in a warehouse"""

    STATUS_CHOICES = [
        ("EMPTY", "Empty"),
        ("ALMOST_OUT", "Almost Out"),
        ("GOOD", "Good"),
        ("FULL", "Full"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stocks"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="stocks"
    )
    quantity_on_hand = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="EMPTY")
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Stock"
        verbose_name_plural = "Stocks"
        unique_together = ("product", "warehouse")
        indexes = [
            models.Index(
                fields=["warehouse", "status"], name="stock_warehouse_status_idx"
            ),
            models.Index(
                fields=["product", "quantity_on_hand"], name="stock_product_qty_idx"
            ),
            models.Index(fields=["last_updated"], name="stock_updated_idx"),
        ]

    def calculate_status(self):
        """Calculate stock status based on quantity"""
        if self.quantity_on_hand <= 0:
            return "EMPTY"
        elif self.quantity_on_hand <= 10:  # Almost out threshold
            return "ALMOST_OUT"
        elif self.quantity_on_hand <= 100:  # Good threshold
            return "GOOD"
        else:
            return "FULL"

    def __str__(self):
        return f"{self.product.name} - {self.quantity_on_hand}{self.product.unit_of_measure} in {self.warehouse.name}"


class Batch(models.Model):
    """Represents a specific lot of a product in a warehouse"""

    def generate_batch_number():
        """Generate a unique batch number."""
        return str(uuid.uuid4()).split("-")[0].upper()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="batches"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="batches"
    )
    batch_number = models.CharField(
        max_length=100, default=generate_batch_number, unique=True
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Batch"
        verbose_name_plural = "Batches"
        unique_together = ("product", "warehouse", "batch_number")
        indexes = [
            models.Index(
                fields=["warehouse", "expiry_date"], name="batch_warehouse_expiry_idx"
            ),
            models.Index(
                fields=["product", "expiry_date"], name="batch_product_expiry_idx"
            ),
            models.Index(fields=["batch_number"], name="batch_number_idx"),
        ]

    def __str__(self):
        return (
            f"Batch {self.batch_number} of {self.product.name} in {self.warehouse.name}"
        )


class StockMovement(models.Model):
    """Audit trail for all stock transactions"""

    MOVEMENT_TYPE_CHOICES = [
        ("IN", "Stock In"),
        ("OUT", "Stock Out"),
        ("ADJUSTMENT", "Adjustment"),
        ("RETURN", "Return"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=50, choices=MOVEMENT_TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    reference_number = models.CharField(
        max_length=100, null=True, blank=True
    )  # PO number, invoice, etc.
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Stock Movement"
        verbose_name_plural = "Stock Movements"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["batch", "created_at"], name="movement_batch_date_idx"
            ),
            models.Index(
                fields=["movement_type", "created_at"], name="movement_type_date_idx"
            ),
            models.Index(fields=["reference_number"], name="movement_ref_idx"),
        ]

    def __str__(self):
        return f"{self.movement_type}: {self.quantity} of {self.batch.product.name} on {self.created_at}"


class ProductReorderPolicy(models.Model):
    """Defines reorder policies for products in warehouses"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reorder_policies"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="reorder_policies"
    )
    min_stock_level = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )  # Minimum quantity to trigger reorder
    reorder_qty = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )  # Quantity to reorder
    lead_time_days = models.IntegerField(
        default=0
    )  # Supplier lead time in days
    safety_stock_qty = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )  # Safety stock quantity
    is_active = models.BooleanField(default=True)  # Is this policy active
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reorder_policies",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_reorder_policies",
    )

    class Meta:
        verbose_name = "Product Reorder Policy"
        verbose_name_plural = "Product Reorder Policies"
        unique_together = ("product", "warehouse")
        indexes = [
            models.Index(
                fields=["warehouse", "is_active"],
                name="reorder_warehouse_active_idx",
            ),
            models.Index(
                fields=["product", "min_stock_level"],
                name="reorder_product_point_idx",
            ),
        ]

    def __str__(self):
        return f"Reorder Policy for {self.product.name} in {self.warehouse.name}"


class InventoryAlert(models.Model):
    """Alerts for inventory levels"""

    ALERT_TYPE_CHOICES = [
        ("LOW_STOCK", "Low Stock"),
        ("OUT_OF_STOCK", "Out of Stock"),
        ("EXPIRY", "Expiry Alert"),
    ]

    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("ACKNOWLEDGED", "Acknowledged"),
        ("RESOLVED", "Resolved"),
    ]

    TRIGGER_CHOICES = [
        ("STOCK_MOVEMENT", "Stock Movement"),
        ("SCHEDULED_CHECK", "Scheduled Check"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="inventory_alerts"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="inventory_alerts"
    )
    reorder_policy = models.ForeignKey(
        ProductReorderPolicy,
        on_delete=models.DO_NOTHING,
        related_name="inventory_alerts",
        null=True,
        blank=True,
    )

    alert_type = models.CharField(max_length=50, choices=ALERT_TYPE_CHOICES)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="OPEN")
    current_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    triggered_by = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_inventory_alerts",
    )

    message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_inventory_alerts",
    )

    class Meta:
        verbose_name = "Inventory Alert"
        verbose_name_plural = "Inventory Alerts"
        indexes = [
            models.Index(
                fields=["product", "warehouse"],
                name="inv_alert_product_whouse_idx",
            ),
            models.Index(
                fields=["status"],
                name="inv_alert_status_idx",
            ),
            models.Index(
                fields=["created_at"],
                name="inv_alert_created_at_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Alert: {self.alert_type} for {self.product.name} in {self.warehouse.name}"
        )
