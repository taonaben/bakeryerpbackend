from django.db import models
import uuid
from central.models import Product, Warehouse
from apps.formulation.models import Formula
from django.db.models import F

# from django.contrib.auth import get_user_model
from django.conf import settings


class ProductionOrder(models.Model):

    production_status_choices = [
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.FloatField()
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    formula = models.ForeignKey(Formula, on_delete=models.PROTECT)
    planned_order = models.OneToOneField(
        "orders.PlannedOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="production_order",
    )
    status = models.CharField(
        max_length=50, choices=production_status_choices, default="scheduled"
    )
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Production Order for {self.product.name} - {self.quantity} units"


class ProductionBatch(models.Model):
    """Model to represent individual production batches for a production order, allowing tracking of batch-specific details and status"""

    batch_status_choices = [
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_order = models.ForeignKey(
        ProductionOrder, related_name="batches", on_delete=models.CASCADE
    )
    batch_number = models.CharField(max_length=100)
    quantity_produced = models.FloatField()
    status = models.CharField(
        max_length=50, choices=batch_status_choices, default="in_progress"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Batch {self.batch_number} for {self.production_order.product.name}"


class ProductionBatchLine(models.Model):
    """Model to represent individual lines in a production batch, similar to formula lines but specific to the batch execution"""

    line_type_choices = [
        ("TEXT", "Text"),
        ("INSTRUCTION", "Instruction"),
        ("MATERIAL", "Material"),
        ("BYPRODUCT", "Byproduct"),
        ("PROCESS", "Process"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_batch = models.ForeignKey(
        ProductionBatch, related_name="lines", on_delete=models.CASCADE
    )
    sequence = models.IntegerField()
    line_type = models.CharField(max_length=50, choices=line_type_choices)
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL
    )
    quantity = models.FloatField()
    text = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.line_type} - {self.quantity} units for Batch {self.production_batch.batch_number}"


class BatchMaterial(models.Model):
    """Model to track materials used in each production batch"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_batch = models.ForeignKey(
        ProductionBatch, related_name="materials", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity_used = models.FloatField()

    def __str__(self):
        return f"{self.product.name} - {self.quantity_used} units for Batch {self.production_batch.batch_number}"


class BatchOutput(models.Model):
    """Model to track outputs produced in each production batch, including finished goods and byproducts"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_batch = models.ForeignKey(
        ProductionBatch, related_name="outputs", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity_produced = models.FloatField()

    def __str__(self):
        return f"{self.product.name} - {self.quantity_produced} units produced in Batch {self.production_batch.batch_number}"


class BatchWaste(models.Model):
    """Model to track waste generated in each production batch, allowing for better analysis of production efficiency and sustainability"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_batch = models.ForeignKey(
        ProductionBatch, related_name="waste", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity_wasted = models.FloatField()
    reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity_wasted} units wasted in Batch {self.production_batch.batch_number}"


class ReworkOrder(models.Model):
    """Order to rework existing inventory lots into a corrected output lot."""

    rework_status_choices = [
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity_requested = models.FloatField(null=True, blank=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=50, choices=rework_status_choices, default="scheduled"
    )
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Rework Order for {self.target_product.name} ({self.status})"


class ReworkInput(models.Model):
    """Input lots consumed during rework."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rework_order = models.ForeignKey(
        ReworkOrder, related_name="inputs", on_delete=models.CASCADE
    )
    batch = models.ForeignKey("inventory.Batch", on_delete=models.PROTECT)
    quantity_used = models.FloatField()
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Rework input {self.batch.batch_number} - {self.quantity_used} units"


class ReworkOutput(models.Model):
    """Output lots produced during rework."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rework_order = models.ForeignKey(
        ReworkOrder, related_name="outputs", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity_produced = models.FloatField()
    output_batch = models.ForeignKey(
        "inventory.Batch", on_delete=models.PROTECT, null=True, blank=True
    )

    def __str__(self):
        return f"Rework output {self.product.name} - {self.quantity_produced} units"
