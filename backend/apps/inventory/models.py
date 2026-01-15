from django.db import models
import uuid
from central.models import Product, Warehouse
from django.db.models import F


class Stock(models.Model):
    """Represents current inventory levels of a product in a warehouse"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="stocks"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="stocks"
    )
    quantity_on_hand = models.DecimalField(max_digits=10,  decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Stock"
        verbose_name_plural = "Stocks"
        unique_together = ("product", "warehouse")

    def __str__(self):
        return f"{self.product.name} - {self.quantity_on_hand}{self.product.unit_of_measure} in {self.warehouse.name}"


class Batch(models.Model):
    """Represents a specific lot of a product in a warehouse"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="batches"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="batches"
    )
    batch_number = models.CharField(max_length=100)
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
    
    def save(self, *args, **kwargs):
        """Override save to automatically adjust stock"""
        # Validate movement doesn't exceed batch quantity
        if self.quantity > self.batch.quantity:
            raise ValueError(f"Movement quantity {self.quantity} exceeds batch quantity {self.batch.quantity}")
        
        # For OUT movements, ensure stock won't go negative
        if self.movement_type == "OUT":
            stock = Stock.objects.filter(
                product=self.batch.product, 
                warehouse=self.batch.warehouse
            ).first()
            if stock and (stock.quantity_on_hand - self.quantity) < 0:
                raise ValueError("Insufficient stock for this movement")
        
        super().save(*args, **kwargs)
        self.adjust_stock()
    
    def adjust_stock(self):
        """Atomically adjust stock levels based on movement type"""
        quantity_delta = self.get_quantity_delta()
        
        if quantity_delta == 0:
            return
        
        # Atomic update using F() to prevent race conditions
        Stock.objects.filter(
            product=self.batch.product,
            warehouse=self.batch.warehouse
        ).update(quantity_on_hand=F('quantity_on_hand') + quantity_delta)
        
        # If Stock doesn't exist, create it
        if not Stock.objects.filter(
            product=self.batch.product,
            warehouse=self.batch.warehouse
        ).exists():
            Stock.objects.create(
                product=self.batch.product,
                warehouse=self.batch.warehouse,
                quantity_on_hand=quantity_delta
            )
    
    def get_quantity_delta(self):
        """Determine quantity change based on movement type"""
        if self.movement_type in ("IN", "RETURN"):
            return self.quantity
        elif self.movement_type == "OUT":
            return -self.quantity
        elif self.movement_type == "ADJUSTMENT":
            return self.quantity  # Can be positive or negative
        return 0

    class Meta:
        verbose_name = "Stock Movement"
        verbose_name_plural = "Stock Movements"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.movement_type}: {self.quantity} of {self.batch.product.name} on {self.created_at}"
