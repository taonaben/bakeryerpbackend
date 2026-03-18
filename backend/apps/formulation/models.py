from django.db import models
import uuid
from central.models import Product
from django.db.models import F

# from django.contrib.auth import get_user_model
from django.conf import settings


class Formula(models.Model):

    formula_status_choices = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("archived", "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    revision = models.IntegerField()
    batch_size = models.FloatField()
    yield_percentage = models.FloatField()
    status = models.CharField(
        max_length=50, choices=formula_status_choices, default="draft"
    )
    created_at = models.DateTimeField(auto_now_add=True)

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
    sequence = models.IntegerField()
    line_type = models.CharField(max_length=50, choices=line_type_choices)
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL
    )
    quantity = models.FloatField()
    text = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.line_type} - {self.quantity} units"
