from django.db import models
import uuid
from central.models import Product


class Formula(models.Model):

    formula_status_choices = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("on_hold", "On Hold"),
        ("deactivated", "Deactivated"),
        ("archived", "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    revision = models.PositiveIntegerField()
    batch_size = models.FloatField()
    yield_percentage = models.FloatField()
    labor_minutes_per_batch = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=50, choices=formula_status_choices, default="draft"
    )
    is_active = models.BooleanField(default=True)
    on_hold = models.BooleanField(default=False)
    on_hold_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "revision"],
                name="unique_formula_product_revision",
            )
        ]

    def __str__(self):
        return f"{self.product.name} - Revision {self.revision}"


class FormulaLine(models.Model):
    line_type_choices = [
        ("TEXT", "Text"),
        ("INSTRUCTION", "Instruction"),
        ("MATERIAL", "Material"),
        ("BYPRODUCT", "Byproduct"),
        ("PROCESS", "Process"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    formula = models.ForeignKey(Formula, related_name="lines", on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField()
    line_type = models.CharField(max_length=50, choices=line_type_choices)
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL
    )
    quantity = models.FloatField(blank=True, null=True)
    text = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.line_type} - {self.quantity} units"
