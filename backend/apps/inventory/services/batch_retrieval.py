from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Batch, StockMovement, StockMovementBatch, ProductPolicy


def create_stock_movement_with_policy(product, warehouse, movement_type, quantity, reference=None, notes=None):
    """
    Create a single stock movement following the product's retrieval policy.
    Automatically distributes quantity across multiple batches if needed.
    """
    # Get retrieval policy
    try:
        policy = ProductPolicy.objects.get(
            product=product,
            warehouse=warehouse,
            is_active=True
        )
        retrieval_method = policy.retrieval_method
    except ProductPolicy.DoesNotExist:
        retrieval_method = "FIFO"
    
    # Get available batches based on retrieval method
    batches = Batch.objects.filter(
        product=product,
        warehouse=warehouse,
        quantity__gt=0
    )
    
    if retrieval_method == "FIFO":
        batches = batches.order_by('created_at')
    elif retrieval_method == "LIFO":
        batches = batches.order_by('-created_at')
    elif retrieval_method == "FEFO":
        batches = batches.filter(expiry_date__isnull=False).order_by('expiry_date')
     
    # Check total available quantity
    total_available = sum(batch.quantity for batch in batches)
    if total_available < quantity:
        raise ValidationError(f"Insufficient stock. Available: {total_available}, Required: {quantity}")
    
    with transaction.atomic():
        # Create the stock movement
        movement = StockMovement.objects.create(
            movement_type=movement_type,
            total_quantity=quantity,
            reference_number=reference,
            notes=notes
        )
        
        # Distribute quantity across batches
        remaining_qty = quantity
        for batch in batches:
            if remaining_qty <= 0:
                break
                
            # Use min of batch quantity or remaining needed quantity
            batch_qty = min(batch.quantity, remaining_qty)
            
            # Create the through model record
            StockMovementBatch.objects.create(
                stock_movement=movement,
                batch=batch,
                quantity=batch_qty
            )
            
            remaining_qty -= batch_qty
    
    return movement