from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from ..models import StockMovement, Stock, ProductReorderPolicy, InventoryAlert
from django.utils import timezone


@receiver(post_save, sender=StockMovement)
def check_inventory_alerts(sender, instance, created, **kwargs):
    """Check and create inventory alerts based on stock levels after movement"""
    if not created:
        return

    product = instance.batch.product
    warehouse = instance.batch.warehouse

    # Get current stock level
    try:
        stock = Stock.objects.get(product=product, warehouse=warehouse)
    except Stock.DoesNotExist:
        return

    current_qty = stock.quantity_on_hand

    # Check for reorder policy
    try:
        policy = ProductReorderPolicy.objects.get(
            product=product, warehouse=warehouse, is_active=True
        )
    except ProductReorderPolicy.DoesNotExist:
        policy = None

    # Determine alert type and create if needed
    alert_type = None
    message = None

    if current_qty <= 0:
        alert_type = "OUT_OF_STOCK"
        message = f"{product.name} is out of stock in {warehouse.name}"
    elif policy and current_qty <= policy.min_stock_level:
        alert_type = "LOW_STOCK"
        message = f"{product.name} in {warehouse.name} has reached minimum stock level ({current_qty}{product.unit_of_measure} <= {policy.min_stock_level}{product.unit_of_measure})"

    # Handle alerts based on stock level
    if alert_type:
        # Create alert if needed and doesn't already exist
        existing_alert = InventoryAlert.objects.filter(
            product=product, warehouse=warehouse, alert_type=alert_type, status="OPEN"
        ).first()

        if not existing_alert:
            InventoryAlert.objects.create(
                product=product,
                warehouse=warehouse,
                reorder_policy=policy,
                alert_type=alert_type,
                message=message,
                current_quantity=current_qty,
                triggered_by="STOCK_MOVEMENT",
            )
    else:
        # Stock is replenished, resolve any open alerts for this product/warehouse
        InventoryAlert.objects.filter(
            product=product,
            warehouse=warehouse,
            status__in=["OPEN", "ACKNOWLEDGED"],
            alert_type__in=["LOW_STOCK", "OUT_OF_STOCK"]
        ).update(
            status="RESOLVED",
            resolved_at=timezone.now()
        )
