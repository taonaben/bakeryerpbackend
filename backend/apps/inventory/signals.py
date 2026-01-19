from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.db.models import F, Sum
from .models import StockMovement, Stock, Batch
from django.core.exceptions import ValidationError


@receiver(post_save, sender=Batch)
def update_stock_on_batch_create(sender, instance, created, **kwargs):
    """Update stock totals when batch is created or updated"""
    with transaction.atomic():
        # Calculate total quantity for this product in this warehouse
        total_quantity = Batch.objects.filter(
            product=instance.product,
            warehouse=instance.warehouse
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # Create temporary stock to calculate status
        temp_stock = Stock(quantity_on_hand=total_quantity)
        status = temp_stock.calculate_status()
        
        # Update or create stock record
        Stock.objects.update_or_create(
            product=instance.product,
            warehouse=instance.warehouse,
            defaults={'quantity_on_hand': total_quantity, 'status': status}
        )


@receiver(post_delete, sender=Batch)
def update_stock_on_batch_delete(sender, instance, **kwargs):
    """Update stock totals when batch is deleted"""
    with transaction.atomic():
        # Calculate remaining total quantity
        total_quantity = Batch.objects.filter(
            product=instance.product,
            warehouse=instance.warehouse
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # Update or delete stock record
        if total_quantity > 0:
            temp_stock = Stock(quantity_on_hand=total_quantity)
            status = temp_stock.calculate_status()
            Stock.objects.update_or_create(
                product=instance.product,
                warehouse=instance.warehouse,
                defaults={'quantity_on_hand': total_quantity, 'status': status}
            )
        else:
            Stock.objects.filter(
                product=instance.product,
                warehouse=instance.warehouse
            ).delete()


@receiver(pre_save, sender=StockMovement)
def validate_stock_movement(sender, instance, **kwargs):
    """Validate stock movement before saving"""
    # For OUT movements, ensure sufficient stock
    if instance.movement_type == "OUT":
        current_stock = Stock.objects.filter(
            product=instance.batch.product,
            warehouse=instance.batch.warehouse
        ).first()
        
        if not current_stock or current_stock.quantity_on_hand < instance.quantity:
            raise ValidationError("Insufficient stock for this movement")
    
    # Validate batch has sufficient quantity for OUT movements
    if instance.movement_type == "OUT" and instance.quantity > instance.batch.quantity:
        raise ValidationError(f"Movement quantity {instance.quantity} exceeds batch quantity {instance.batch.quantity}")


@receiver(post_save, sender=StockMovement)
def update_stock_and_batch(sender, instance, created, **kwargs):
    """Update stock and batch quantities after stock movement"""
    if not created:
        return
    
    with transaction.atomic():
        # Update batch quantity for OUT movements
        if instance.movement_type == "OUT":
            Batch.objects.filter(id=instance.batch.id).update(
                quantity=F('quantity') - instance.quantity
            )
        
        # Recalculate stock total from all batches
        total_quantity = Batch.objects.filter(
            product=instance.batch.product,
            warehouse=instance.batch.warehouse
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        temp_stock = Stock(quantity_on_hand=total_quantity)
        status = temp_stock.calculate_status()
        
        Stock.objects.update_or_create(
            product=instance.batch.product,
            warehouse=instance.batch.warehouse,
            defaults={'quantity_on_hand': total_quantity, 'status': status}
        )


@receiver(post_delete, sender=StockMovement)
def reverse_stock_movement(sender, instance, **kwargs):
    """Reverse stock changes when movement is deleted"""
    with transaction.atomic():
        # Reverse batch quantity for OUT movements
        if instance.movement_type == "OUT":
            Batch.objects.filter(id=instance.batch.id).update(
                quantity=F('quantity') + instance.quantity
            )
        
        # Recalculate stock total from all batches
        total_quantity = Batch.objects.filter(
            product=instance.batch.product,
            warehouse=instance.batch.warehouse
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        temp_stock = Stock(quantity_on_hand=total_quantity)
        status = temp_stock.calculate_status()
        
        Stock.objects.update_or_create(
            product=instance.batch.product,
            warehouse=instance.batch.warehouse,
            defaults={'quantity_on_hand': total_quantity, 'status': status}
        )


def get_quantity_delta(movement):
    """Calculate quantity change based on movement type"""
    if movement.movement_type in ("IN", "RETURN"):
        return movement.quantity
    elif movement.movement_type == "OUT":
        return -movement.quantity
    elif movement.movement_type == "ADJUSTMENT":
        return movement.quantity  # Can be positive or negative
    return 0