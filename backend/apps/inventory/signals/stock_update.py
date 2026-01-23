from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.db.models import F
from ..models import StockMovement, Stock, Batch
from ..utils import recalculate_stock_for_product_warehouse


@receiver(post_save, sender=Batch)
def update_stock_on_batch_create(sender, instance, created, **kwargs):
    """Update stock totals when batch is created or updated"""
    recalculate_stock_for_product_warehouse(instance.product, instance.warehouse)


@receiver(post_delete, sender=Batch)
def update_stock_on_batch_delete(sender, instance, **kwargs):
    """Update stock totals when batch is deleted"""
    recalculate_stock_for_product_warehouse(instance.product, instance.warehouse)
    
    


@receiver(post_save, sender=StockMovement)
def update_stock_and_batch(sender, instance, created, **kwargs):
    """Update stock and batch quantities after stock movement"""
    if not created:
        return

    with transaction.atomic():
        # Update batch quantities for each batch in the movement
        for movement_batch in instance.stockmovementbatch_set.all():
            batch = movement_batch.batch
            quantity = movement_batch.quantity
            
            if instance.movement_type == "OUT" or instance.movement_type == "RETURN":
                Batch.objects.filter(id=batch.id).update(
                    quantity=F("quantity") - quantity
                )
            elif instance.movement_type == "IN":
                Batch.objects.filter(id=batch.id).update(
                    quantity=F("quantity") + quantity
                )
            elif instance.movement_type == "ADJUSTMENT":
                Batch.objects.filter(id=batch.id).update(
                    quantity=F("quantity") + quantity
                )
            
            # Recalculate stock totals for each affected product/warehouse
            recalculate_stock_for_product_warehouse(batch.product, batch.warehouse)


@receiver(post_delete, sender=StockMovement)
def reverse_stock_movement(sender, instance, **kwargs):
    """Reverse stock changes when movement is deleted"""
    with transaction.atomic():
        # Reverse changes for each batch in the movement
        for movement_batch in instance.stockmovementbatch_set.all():
            batch = movement_batch.batch
            quantity = movement_batch.quantity
            
            try:
                if instance.movement_type == "OUT":
                    Batch.objects.filter(id=batch.id).update(
                        quantity=F("quantity") + quantity
                    )
            except Batch.DoesNotExist:
                pass  # Batch was already deleted, skip reversal
            
            # Recalculate stock totals
            recalculate_stock_for_product_warehouse(batch.product, batch.warehouse)
