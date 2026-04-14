from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from ..models import Batch, StockMovementBatch
from ..services.stock_movement_service import (
    apply_movement_batch,
    reverse_movement_batch,
    update_stock_for_batch,
)


@receiver(post_save, sender=Batch)
def update_stock_on_batch_create(sender, instance, created, **kwargs):
    """Update stock totals when batch is created or updated"""
    update_stock_for_batch(instance)


@receiver(post_delete, sender=Batch)
def update_stock_on_batch_delete(sender, instance, **kwargs):
    """Update stock totals when batch is deleted"""
    update_stock_for_batch(instance)


@receiver(post_save, sender=StockMovementBatch)
def update_batch_quantity(sender, instance, created, **kwargs):
    """Update batch quantities when StockMovementBatch is created"""
    if not created:
        return
    apply_movement_batch(instance)


@receiver(post_delete, sender=StockMovementBatch)
def reverse_batch_quantity(sender, instance, **kwargs):
    """Reverse batch quantity changes when StockMovementBatch is deleted"""
    reverse_movement_batch(instance)
