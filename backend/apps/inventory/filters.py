import django_filters
from .models import Stock, StockMovement, Batch


class StockFilter(django_filters.FilterSet):
    """
    FilterSet for Stock model to filter by warehouse ID.
    """

    class Meta:
        model = Stock
        fields = {
            "warehouse_id": ["exact"],
            "product__sku": ["exact", "icontains"],
            "quantity_on_hand": ["exact", "gt", "lt", "gte", "lte"],
            "status": ["exact"],
            "created_at": ["exact", "gt", "lt", "gte", "lte"],
        }


class StockMovementFilter(django_filters.FilterSet):
    """
    FilterSet for StockMovement model to filter by warehouse ID.
    """

    class Meta:
        model = StockMovement
        fields = {
            "batch__warehouse_id": ["exact"],
            "batch__product__sku": ["exact", "icontains"],
            "movement_type": ["exact"],
            "notes": ["icontains"],
            "quantity": ["exact", "gt", "lt", "gte", "lte"],
            "created_at": ["exact", "gt", "lt", "gte", "lte"],
        }


class BatchFilter(django_filters.FilterSet):
    """
    FilterSet for Batch model to filter by warehouse ID.
    """

    class Meta:
        model = Batch
        fields = {
            "warehouse_id": ["exact"],
            "product__sku": ["exact", "icontains"],
            "batch_number": ["exact", "icontains"],
            "manufacture_date": ["exact", "gt", "lt", "gte", "lte", "range"],
            "expiry_date": ["exact", "gt", "lt", "gte", "lte", "range"],
            "created_at": ["exact", "gt", "lt", "gte", "lte", "range"],
        }
