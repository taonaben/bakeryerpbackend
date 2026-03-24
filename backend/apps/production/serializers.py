from rest_framework import serializers

from apps.formulation.serializers import FormulaSerializer
from .models import ProductionOrder, ProductionBatch


class ProductionPlanSerializer(serializers.Serializer):
    scale_factor = serializers.DecimalField(max_digits=18, decimal_places=6)
    formula = FormulaSerializer(read_only=True)
    shortages = serializers.DictField(child=serializers.DictField(), read_only=True)
    validation_errors = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    can_run = serializers.BooleanField(read_only=True)


class ProductionOrderSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = ProductionOrder
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "status",
            "scheduled_start",
            "scheduled_end",
            "warehouse",
            "warehouse_name",
            "formula",
        ]

        read_only_fields = ["id", "status"]


class SelectedBatchAllocationSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    batch_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)


class StartProductionSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6, required=False)
    selected_batches = SelectedBatchAllocationSerializer(many=True, required=False)


class ProductionBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionBatch
        fields = [
            "id",
            "production_order",
            "batch_number",
            "quantity_produced",
            "status",
            "started_at",
            "completed_at",
        ]
