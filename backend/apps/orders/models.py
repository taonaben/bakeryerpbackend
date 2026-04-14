import uuid

from django.conf import settings
from django.db import models

from central.models import Product, Warehouse


class PlannedOrder(models.Model):
    status_choices = [
        ("draft", "Draft"),
        ("planned", "Planned"),
        ("started", "Started"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    priority_choices = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=18, decimal_places=6)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    need_by = models.DateTimeField()
    priority = models.CharField(
        max_length=20, choices=priority_choices, default="normal"
    )
    status = models.CharField(max_length=20, choices=status_choices, default="draft")
    priority_override_requested_at = models.DateTimeField(null=True, blank=True)
    priority_override_approved_at = models.DateTimeField(null=True, blank=True)
    priority_override_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_planned_order_overrides",
    )
    priority_override_note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["need_by", "created_at"]
        indexes = [
            models.Index(fields=["status", "need_by"], name="planned_status_need_idx"),
            models.Index(fields=["warehouse", "need_by"], name="planned_wh_need_idx"),
        ]

    def __str__(self):
        return f"Planned Order for {self.product.name} - {self.quantity} units"
