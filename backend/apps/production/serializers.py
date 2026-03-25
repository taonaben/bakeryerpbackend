from decimal import Decimal

from rest_framework import serializers

from central.models import Product
from apps.formulation.serializers import FormulaSerializer
from .models import (
    ProductionOrder,
    ProductionBatch,
    ProductionBatchLine,
    BatchMaterial,
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


class ProductionBatchLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = ProductionBatchLine
        fields = [
            "id",
            "sequence",
            "line_type",
            "product",
            "product_name",
            "quantity",
            "text",
        ]


class BatchMaterialSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = BatchMaterial
        fields = ["id", "product", "product_name", "quantity_used"]


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


class ProductionBatchDetailSerializer(serializers.ModelSerializer):
    lines = ProductionBatchLineSerializer(many=True, read_only=True)
    materials = BatchMaterialSerializer(many=True, read_only=True)
    outputs = BatchOutputSerializer(many=True, read_only=True)
    waste = BatchWasteSerializer(many=True, read_only=True)

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
            "lines",
            "materials",
            "outputs",
            "waste",
        ]


class ProductionOrderFinishedSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    batches = ProductionBatchDetailSerializer(many=True, read_only=True)
    expected_output = serializers.SerializerMethodField()
    expected_waste = serializers.SerializerMethodField()
    actual_output = serializers.SerializerMethodField()
    actual_waste = serializers.SerializerMethodField()
    variance = serializers.SerializerMethodField()

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
            "expected_output",
            "expected_waste",
            "actual_output",
            "actual_waste",
            "variance",
            "batches",
        ]
        read_only_fields = fields

    def get_expected_output(self, obj):
        return Decimal(str(obj.quantity or 0))

    def get_expected_waste(self, obj):
        expected_output = Decimal(str(obj.quantity or 0))
        yield_pct = Decimal(str(getattr(obj.formula, "yield_percentage", 0) or 0))
        return expected_output * (Decimal("100") - yield_pct) / Decimal("100")

    def get_actual_output(self, obj):
        total = Decimal("0")
        for batch in obj.batches.all():
            for output in batch.outputs.all():
                if output.product_id == obj.product_id:
                    total += Decimal(str(output.quantity_produced or 0))
        return total

    def get_actual_waste(self, obj):
        total = Decimal("0")
        for batch in obj.batches.all():
            for waste in batch.waste.all():
                total += Decimal(str(waste.quantity_wasted or 0))
        return total

    def get_variance(self, obj):
        return self.get_expected_output(obj) - self.get_actual_output(obj)
