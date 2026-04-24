from rest_framework import serializers
from apps.costing.models import CostingEntry, CostingEntryLine


class CostingEntryLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = CostingEntryLine
        fields = [
            "id",
            "product",
            "product_name",
            "batch_material",
            "actual_quantity_used",
            "unit_price_used",
            "actual_cost",
        ]
        read_only_fields = fields


class CostingEntrySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    batch_number = serializers.CharField(
        source="production_batch.batch_number", read_only=True
    )
    lines = CostingEntryLineSerializer(many=True, read_only=True)

    class Meta:
        model = CostingEntry
        fields = [
            "id",
            "production_batch",
            "batch_number",
            "product",
            "product_name",
            "warehouse",
            "warehouse_name",
            "standard_cost",
            "overhead_rate",
            "total_material_cost",
            "overhead_cost",
            "total_cost",
            "actual_output_quantity",
            "actual_waste_quantity",
            "cost_per_unit",
            "computed_at",
            "currency",
            "lines",
        ]
        read_only_fields = fields


class CostingEntryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    batch_number = serializers.CharField(
        source="production_batch.batch_number", read_only=True
    )

    class Meta:
        model = CostingEntry
        fields = [
            "id",
            "production_batch",
            "batch_number",
            "product",
            "product_name",
            "warehouse",
            "warehouse_name",
            "total_cost",
            "cost_per_unit",
            "actual_output_quantity",
            "currency",
            "computed_at",
        ]
        read_only_fields = fields


class ComputeCostingEntrySerializer(serializers.Serializer):
    """Input for the manual compute trigger endpoint."""
    production_batch_id = serializers.UUIDField()
    force = serializers.BooleanField(default=False, required=False)

    def validate_production_batch_id(self, value):
        from apps.production.models import ProductionBatch
        if not ProductionBatch.objects.filter(pk=value).exists():
            raise serializers.ValidationError("ProductionBatch not found.")
        return value
