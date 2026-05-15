from rest_framework import serializers
from apps.costing.models import CostVarianceRecord


class CostVarianceRecordSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    batch_number = serializers.CharField(
        source="production_batch.batch_number", read_only=True
    )

    class Meta:
        model = CostVarianceRecord
        fields = [
            "id",
            "costing_entry",
            "standard_cost",
            "production_batch",
            "batch_number",
            "product",
            "product_name",
            "warehouse",
            "warehouse_name",
            "material_price_variance",
            "material_usage_variance",
            "yield_variance",
            "overhead_variance",
            "total_variance",
            "variance_percentage",
            "is_favourable",
            "computed_at",
        ]
        read_only_fields = fields


class VarianceSummarySerializer(serializers.Serializer):
    """Output shape for the aggregated variance summary endpoint."""
    group_by = serializers.CharField()
    group_id = serializers.UUIDField()
    group_name = serializers.CharField()
    total_variance = serializers.DecimalField(max_digits=14, decimal_places=4)
    avg_variance_percentage = serializers.DecimalField(max_digits=9, decimal_places=4)
    favourable_count = serializers.IntegerField()
    adverse_count = serializers.IntegerField()
    batch_count = serializers.IntegerField()
