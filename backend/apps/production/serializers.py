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
    ReworkOrder,
    ReworkInput,
    ReworkOutput,
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
    planned_order_status = serializers.CharField(
        source="planned_order.status", read_only=True
    )
    formula_name = serializers.SerializerMethodField()

    def get_formula_name(self, obj):
        if obj.formula:
            return obj.formula.name
        return None

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
            "formula_name",
            "planned_order",
            "planned_order_status",
        ]

        read_only_fields = ["id", "status", "planned_order_status", "formula_name"]


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


class ReworkInputLineSerializer(serializers.Serializer):
    batch_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ReworkOutputLineSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)


class StartReworkSerializer(serializers.Serializer):
    inputs = ReworkInputLineSerializer(many=True)

    def validate_inputs(self, inputs):
        if not inputs:
            raise serializers.ValidationError("At least one input line is required.")
        for line in inputs:
            if line["quantity"] <= 0:
                raise serializers.ValidationError(
                    "Input quantity must be greater than 0."
                )
        return inputs


class FinishReworkSerializer(serializers.Serializer):
    outputs = ReworkOutputLineSerializer(many=True)

    def validate_outputs(self, outputs):
        if not outputs:
            raise serializers.ValidationError("At least one output line is required.")
        for line in outputs:
            if line["quantity"] <= 0:
                raise serializers.ValidationError(
                    "Output quantity must be greater than 0."
                )
        return outputs


class ReworkOrderSerializer(serializers.ModelSerializer):
    target_product_name = serializers.CharField(
        source="target_product.name", read_only=True
    )
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = ReworkOrder
        fields = [
            "id",
            "target_product",
            "target_product_name",
            "quantity_requested",
            "warehouse",
            "warehouse_name",
            "status",
            "reason",
            "created_at",
            "completed_at",
        ]
        read_only_fields = ["id", "status", "created_at", "completed_at"]


class ReworkInputSerializer(serializers.ModelSerializer):
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)
    product_name = serializers.CharField(source="batch.product.name", read_only=True)

    class Meta:
        model = ReworkInput
        fields = [
            "id",
            "batch",
            "batch_number",
            "product_name",
            "quantity_used",
            "notes",
        ]


class ReworkOutputSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    output_batch_number = serializers.CharField(
        source="output_batch.batch_number", read_only=True
    )

    class Meta:
        model = ReworkOutput
        fields = [
            "id",
            "product",
            "product_name",
            "quantity_produced",
            "output_batch",
            "output_batch_number",
        ]


class ReworkOrderDetailSerializer(serializers.ModelSerializer):
    target_product_name = serializers.CharField(
        source="target_product.name", read_only=True
    )
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    inputs = ReworkInputSerializer(many=True, read_only=True)
    outputs = ReworkOutputSerializer(many=True, read_only=True)

    class Meta:
        model = ReworkOrder
        fields = [
            "id",
            "target_product",
            "target_product_name",
            "quantity_requested",
            "warehouse",
            "warehouse_name",
            "status",
            "reason",
            "created_at",
            "completed_at",
            "inputs",
            "outputs",
        ]
        read_only_fields = fields


class ProductionCountByStatusSerializer(serializers.Serializer):
    scheduled = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    completed = serializers.IntegerField()
    cancelled = serializers.IntegerField()


class ProductionExpectedActualSerializer(serializers.Serializer):
    expected_output = serializers.DecimalField(max_digits=18, decimal_places=6)
    actual_output = serializers.DecimalField(max_digits=18, decimal_places=6)


class ProductionWasteSummarySerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    waste_rate = serializers.DecimalField(
        max_digits=9, decimal_places=4, allow_null=True
    )


class ProductionVarianceSummarySerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    variance_rate = serializers.DecimalField(
        max_digits=9, decimal_places=4, allow_null=True
    )


class ProductionProductQuantitySerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    total_quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    batch_count = serializers.IntegerField()


class ProductionOverviewSummarySerializer(serializers.Serializer):
    as_of_date = serializers.DateField()
    date_from = serializers.DateField(allow_null=True, required=False)
    date_to = serializers.DateField(allow_null=True, required=False)
    warehouse_id = serializers.UUIDField(allow_null=True, required=False)
    production_order_counts_by_status = ProductionCountByStatusSerializer()
    rework_order_counts_by_status = ProductionCountByStatusSerializer()
    wip_order_count = serializers.IntegerField()
    in_progress_batch_count = serializers.IntegerField()
    scheduled_orders_overdue_to_start = serializers.IntegerField()
    completed_quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    expected_vs_actual_output = ProductionExpectedActualSerializer()
    waste = ProductionWasteSummarySerializer()
    variance = ProductionVarianceSummarySerializer()
    top_products_produced = ProductionProductQuantitySerializer(many=True)


class ProductionOverviewOrderSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    warehouse_id = serializers.UUIDField()
    warehouse_name = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    status = serializers.ChoiceField(
        choices=["scheduled", "in_progress", "completed", "cancelled"]
    )
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    formula_id = serializers.UUIDField()
    formula_name = serializers.CharField(allow_null=True)


class ProductionBlockedOrderSerializer(ProductionOverviewOrderSerializer):
    blocking_reasons = serializers.ListField(child=serializers.CharField())


class ProductionOverviewBatchSerializer(serializers.Serializer):
    batch_id = serializers.UUIDField()
    batch_number = serializers.CharField()
    order_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    warehouse_id = serializers.UUIDField()
    warehouse_name = serializers.CharField()
    quantity_produced = serializers.DecimalField(max_digits=18, decimal_places=6)
    status = serializers.ChoiceField(choices=["in_progress", "completed", "failed"])
    started_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)


class ProductionOverviewWIPSerializer(serializers.Serializer):
    as_of_date = serializers.DateField()
    warehouse_id = serializers.UUIDField(allow_null=True, required=False)
    in_progress_orders = ProductionOverviewOrderSerializer(many=True)
    in_progress_batches = ProductionOverviewBatchSerializer(many=True)
    scheduled_orders_due_today = ProductionOverviewOrderSerializer(many=True)
    scheduled_orders_overdue = ProductionOverviewOrderSerializer(many=True)
    orders_blocked_by_unavailable_formula = ProductionBlockedOrderSerializer(
        many=True
    )


class ProductionYieldTrendOutputRowSerializer(serializers.Serializer):
    period = serializers.DateTimeField()
    expected_output = serializers.DecimalField(max_digits=18, decimal_places=6)
    actual_output = serializers.DecimalField(max_digits=18, decimal_places=6)
    variance = serializers.DecimalField(max_digits=18, decimal_places=6)
    completed_orders = serializers.IntegerField()


class ProductionWasteTrendRowSerializer(serializers.Serializer):
    period = serializers.DateTimeField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    line_count = serializers.IntegerField()


class ProductionVarianceByProductSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    expected_output = serializers.DecimalField(max_digits=18, decimal_places=6)
    actual_output = serializers.DecimalField(max_digits=18, decimal_places=6)
    variance = serializers.DecimalField(max_digits=18, decimal_places=6)
    completed_orders = serializers.IntegerField()


class ProductionYieldTrendsSerializer(serializers.Serializer):
    date_from = serializers.DateField(allow_null=True, required=False)
    date_to = serializers.DateField(allow_null=True, required=False)
    warehouse_id = serializers.UUIDField(allow_null=True, required=False)
    interval = serializers.ChoiceField(choices=["day", "week", "month"])
    output = ProductionYieldTrendOutputRowSerializer(many=True)
    waste = ProductionWasteTrendRowSerializer(many=True)
    variance_by_product = ProductionVarianceByProductSerializer(many=True)


class ProductionScheduleAdherenceOrderSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    warehouse_id = serializers.UUIDField()
    warehouse_name = serializers.CharField()
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    first_batch_started_at = serializers.DateTimeField(allow_null=True)
    last_batch_completed_at = serializers.DateTimeField(allow_null=True)
    start_delay_minutes = serializers.FloatField(allow_null=True)
    finish_delay_minutes = serializers.FloatField(allow_null=True)


class ProductionScheduleAdherenceSerializer(serializers.Serializer):
    date_from = serializers.DateField(allow_null=True, required=False)
    date_to = serializers.DateField(allow_null=True, required=False)
    warehouse_id = serializers.UUIDField(allow_null=True, required=False)
    on_time_start_rate = serializers.DecimalField(
        max_digits=9, decimal_places=4, allow_null=True
    )
    on_time_finish_rate = serializers.DecimalField(
        max_digits=9, decimal_places=4, allow_null=True
    )
    orders = ProductionScheduleAdherenceOrderSerializer(many=True)
