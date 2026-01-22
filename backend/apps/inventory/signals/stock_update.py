from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.db.models import F
from ..models import StockMovement, Stock, Batch
from django.core.exceptions import ValidationError
from ..utils import recalculate_stock_for_product_warehouse, get_current_batch_quantity


@receiver(post_save, sender=Batch)
def update_stock_on_batch_create(sender, instance, created, **kwargs):
    """Update stock totals when batch is created or updated"""
    recalculate_stock_for_product_warehouse(instance.product, instance.warehouse)


@receiver(post_delete, sender=Batch)
def update_stock_on_batch_delete(sender, instance, **kwargs):
    """Update stock totals when batch is deleted"""
    recalculate_stock_for_product_warehouse(instance.product, instance.warehouse)


@receiver(pre_save, sender=StockMovement)
def validate_stock_movement(sender, instance, **kwargs):
    """Validate stock movement before saving"""
    # For OUT movements, ensure sufficient stock using batch data
    if instance.movement_type == "OUT":
        current_quantity = get_current_batch_quantity(
            instance.batch.product, instance.batch.warehouse
        )

        if current_quantity < instance.quantity:
            raise ValidationError("Insufficient stock for this movement")

    # Validate batch has sufficient quantity for OUT movements
    if instance.movement_type == "OUT" and instance.quantity > instance.batch.quantity:
        raise ValidationError(
            f"Movement quantity {instance.quantity} exceeds batch quantity {instance.batch.quantity}"
        )


@receiver(post_save, sender=StockMovement)
def update_stock_and_batch(sender, instance, created, **kwargs):
    """Update stock and batch quantities after stock movement"""
    if not created:
        return

    with transaction.atomic():
        # Update batch quantity for OUT movements
        if instance.movement_type == "OUT" or instance.movement_type == "RETURN":
            Batch.objects.filter(id=instance.batch.id).update(
                quantity=F("quantity") - instance.quantity
            )

        if instance.movement_type == "IN":
            Batch.objects.filter(id=instance.batch.id).update(
                quantity=F("quantity") + instance.quantity
            )

        if instance.movement_type == "ADJUSTMENT":
            Batch.objects.filter(id=instance.batch.id).update(
                quantity=F("quantity") + instance.quantity
            )

        # Recalculate stock totals
        recalculate_stock_for_product_warehouse(
            instance.batch.product, instance.batch.warehouse
        )


@receiver(post_delete, sender=StockMovement)
def reverse_stock_movement(sender, instance, **kwargs):
    """Reverse stock changes when movement is deleted"""
    with transaction.atomic():
        # Check if batch still exists before updating
        try:
            if instance.movement_type == "OUT":
                Batch.objects.filter(id=instance.batch.id).update(
                    quantity=F("quantity") + instance.quantity
                )
        except Batch.DoesNotExist:
            pass  # Batch was already deleted, skip reversal

        # Recalculate stock totals
        recalculate_stock_for_product_warehouse(
            instance.batch.product, instance.batch.warehouse
        )
