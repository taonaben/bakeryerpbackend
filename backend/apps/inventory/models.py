from django.db import models
import uuid
from central.models import Product, Warehouse
from django.db.models import F


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
    quantity_on_hand = models.DecimalField(max_digits=10,  decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="EMPTY")
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Stock"
        verbose_name_plural = "Stocks"
        unique_together = ("product", "warehouse")

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
        return str(uuid.uuid4()).split('-')[0].upper()

    
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="batches"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="batches"
    )
    batch_number = models.CharField(max_length=100, default=generate_batch_number, unique=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Batch"
        verbose_name_plural = "Batches"
        unique_together = ("product", "warehouse", "batch_number")

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

    def __str__(self):
        return f"{self.movement_type}: {self.quantity} of {self.batch.product.name} on {self.created_at}"
