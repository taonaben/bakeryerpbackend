from django.db.models import Sum
from django.db import transaction
from django.utils import timezone
from datetime import timedelta


def calculate_stock_status(quantity):
    """Calculate stock status based on quantity without creating temporary objects"""
    if quantity <= 0:
        return "EMPTY"
    elif quantity <= 10:  # Almost out threshold
        return "ALMOST_OUT"
    elif quantity <= 100:  # Good threshold
        return "GOOD"
    else:
        return "FULL"


def recalculate_stock_for_product_warehouse(product, warehouse):
    """
    Recalculate and update stock totals for a product in a warehouse.
    Returns the updated stock record or None if no batches exist.
    """
    from .models import Stock, Batch
    
    with transaction.atomic():
        # Calculate total quantity from all batches
        total_quantity = Batch.objects.filter(
            product=product,
            warehouse=warehouse
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # Calculate status
        status = calculate_stock_status(total_quantity)
        
        # Update or create/delete stock record
        if total_quantity > 0:
            stock, created = Stock.objects.update_or_create(
                product=product,
                warehouse=warehouse,
                defaults={'quantity_on_hand': total_quantity, 'status': status}
            )
            return stock
        else:
            Stock.objects.filter(
                product=product,
                warehouse=warehouse
            ).delete()
            return None


def get_current_batch_quantity(product, warehouse):
    """Get current total quantity from batches for validation purposes"""
    from .models import Batch
    
    return Batch.objects.filter(
        product=product,
        warehouse=warehouse
    ).aggregate(total=Sum('quantity'))['total'] or 0


def check_expiring_batches():
    """Check for batches expiring within 7 days and create alerts"""
    from .models import Batch, InventoryAlert
    
    expiry_threshold = timezone.now().date() + timedelta(days=7)
    
    expiring_batches = Batch.objects.filter(
        expiry_date__lte=expiry_threshold,
        expiry_date__gte=timezone.now().date(),
        quantity__gt=0
    )
    
    for batch in expiring_batches:
        # Check if alert already exists
        existing_alert = InventoryAlert.objects.filter(
            product=batch.product,
            warehouse=batch.warehouse,
            alert_type="EXPIRY",
            status="OPEN"
        ).first()
        
        if not existing_alert:
            InventoryAlert.objects.create(
                product=batch.product,
                warehouse=batch.warehouse,
                alert_type="EXPIRY",
                message=f"Batch {batch.batch_number} of {batch.product.name} expires on {batch.expiry_date}",
                current_quantity=batch.quantity,
                triggered_by="SCHEDULED_CHECK"
            )