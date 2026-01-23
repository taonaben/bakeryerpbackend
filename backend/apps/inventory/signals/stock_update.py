from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.db.models import F
from ..models import StockMovement, Stock, Batch, StockMovementBatch
from ..utils import recalculate_stock_for_product_warehouse


@receiver(post_save, sender=Batch)
def update_stock_on_batch_create(sender, instance, created, **kwargs):
    """Update stock totals when batch is created or updated"""
    recalculate_stock_for_product_warehouse(instance.product, instance.warehouse)


@receiver(post_delete, sender=Batch)
def update_stock_on_batch_delete(sender, instance, **kwargs):
    """Update stock totals when batch is deleted"""
    recalculate_stock_for_product_warehouse(instance.product, instance.warehouse)


@receiver(post_save, sender=StockMovementBatch)
def update_batch_quantity(sender, instance, created, **kwargs):
    """Update batch quantities when StockMovementBatch is created"""
    if not created:
        return

    batch = instance.batch
    quantity = instance.quantity
    movement_type = instance.stock_movement.movement_type
    
    with transaction.atomic():
        if movement_type == "OUT" or movement_type == "RETURN":
            Batch.objects.filter(id=batch.id).update(
                quantity=F("quantity") - quantity
            )
        elif movement_type == "IN":
            Batch.objects.filter(id=batch.id).update(
                quantity=F("quantity") + quantity
            )
        elif movement_type == "ADJUSTMENT":
            Batch.objects.filter(id=batch.id).update(
                quantity=F("quantity") + quantity
            )
        
        # Recalculate stock totals
        recalculate_stock_for_product_warehouse(batch.product, batch.warehouse)


@receiver(post_delete, sender=StockMovementBatch)
def reverse_batch_quantity(sender, instance, **kwargs):
    """Reverse batch quantity changes when StockMovementBatch is deleted"""
    batch = instance.batch
    quantity = instance.quantity
    movement_type = instance.stock_movement.movement_type
    
    with transaction.atomic():
        try:
            if movement_type == "OUT" or movement_type == "RETURN":
                Batch.objects.filter(id=batch.id).update(
                    quantity=F("quantity") + quantity
                )
            elif movement_type == "IN":
                Batch.objects.filter(id=batch.id).update(
                    quantity=F("quantity") - quantity
                )
            elif movement_type == "ADJUSTMENT":
                Batch.objects.filter(id=batch.id).update(
                    quantity=F("quantity") - quantity
                )
        except Batch.DoesNotExist:
            pass  # Batch was already deleted, skip reversal
        
        # Recalculate stock totals
        recalculate_stock_for_product_warehouse(batch.product, batch.warehouse)
