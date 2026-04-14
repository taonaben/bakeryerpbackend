import django_filters
from .models import Stock, StockMovement, Batch


class StockFilter(django_filters.FilterSet):
    """
    FilterSet for Stock model to filter by warehouse ID.
    """

    status = django_filters.BaseInFilter(field_name="status", lookup_expr="in")

    class Meta:
        model = Stock
        fields = {
            "warehouse_id": ["exact"],
            "product__sku": ["exact", "icontains"],
            "quantity_on_hand": ["exact", "gt", "lt", "gte", "lte"],
            "created_at": ["exact", "gt", "lt", "gte", "lte", "range"],
        }


class StockMovementFilter(django_filters.FilterSet):
    """
    FilterSet for StockMovement model to filter by warehouse ID.
    """

    movement_type = django_filters.BaseInFilter(
        field_name="movement_type", lookup_expr="in"
    )

    class Meta:
        model = StockMovement
        fields = {
            "notes": ["icontains"],
            "total_quantity": ["exact", "gt", "lt", "gte", "lte"],
            "created_at": ["exact", "gt", "lt", "gte", "lte", "range"],
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
