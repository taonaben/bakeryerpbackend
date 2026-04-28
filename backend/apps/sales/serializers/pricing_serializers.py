from rest_framework import serializers


class ResolvePriceSerializer(serializers.Serializer):
    """Query params for GET /pricing/resolve"""
    customer_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    warehouse_id = serializers.UUIDField()


class ResolvedPriceSerializer(serializers.Serializer):
    """Response shape for the price resolution endpoint."""
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    customer_id = serializers.UUIDField()
    order_type = serializers.CharField()
    resolved_price = serializers.DecimalField(max_digits=14, decimal_places=2)
    price_source = serializers.ChoiceField(choices=["agreement", "pricing_rule"])
    minimum_selling_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    recommended_selling_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    below_floor = serializers.BooleanField()
    stock_available = serializers.DecimalField(max_digits=10, decimal_places=2)
    sufficient_stock = serializers.BooleanField()
