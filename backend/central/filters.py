import django_filters
from .models import Product, Warehouse


class ProductFilter(django_filters.FilterSet):
    """
    FilterSet for Product model to filter by category and price range.
    """

    class Meta:
        model = Product
        fields = {
            "category": ["exact", "icontains"],
            "name": ["icontains"],
            "unit_of_measure": ["exact"],
            "sku": ["icontains"],
            "created_at": ["exact", "gt", "lt", "gte", "lte"],
        }


class WarehouseFilter(django_filters.FilterSet):
    """
    FilterSet for Warehouse model to filter by company and warehouse type.
    """

    class Meta:
        model = Warehouse
        fields = {
            "name": ["icontains"],
            "wh_type": ["exact", "icontains"],
            "status": ["exact", "icontains"],
            "created_at": ["exact", "gt", "lt", "gte", "lte"],
        }
