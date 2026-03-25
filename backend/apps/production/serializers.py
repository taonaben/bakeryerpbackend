from rest_framework import serializers

from central.models import Product
from apps.formulation.serializers import FormulaSerializer
from .models import (
    ProductionOrder,
    ProductionBatch,
    BatchOutput,
    BatchWaste,
)


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


class ProductionOutputLineSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)


class ProductionWasteLineSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class FinishProductionSerializer(serializers.Serializer):
    outputs = ProductionOutputLineSerializer(many=True)
    waste = ProductionWasteLineSerializer(many=True, required=False)

    def validate_outputs(self, outputs):
        if not outputs:
            raise serializers.ValidationError("At least one output line is required.")
        for line in outputs:
            if line["quantity"] <= 0:
                raise serializers.ValidationError(
                    "Output quantity must be greater than 0."
                )
        return outputs

    def validate_waste(self, waste):
        for line in waste:
            if line["quantity"] <= 0:
                raise serializers.ValidationError(
                    "Waste quantity must be greater than 0."
                )
        return waste


class FinishProductionSummarySerializer(serializers.Serializer):
    actual_output = serializers.DecimalField(max_digits=18, decimal_places=6)
    waste = serializers.DecimalField(max_digits=18, decimal_places=6, required=False)

    def validate_actual_output(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Actual output quantity must be greater than 0."
            )
        return value

    def validate_waste(self, value):
        if value < 0:
            raise serializers.ValidationError("Waste quantity must be 0 or greater.")
        return value


class BatchOutputSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = BatchOutput
        fields = ["id", "product", "product_name", "quantity_produced"]


class BatchWasteSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = BatchWaste
        fields = ["id", "product", "product_name", "quantity_wasted", "reason"]
