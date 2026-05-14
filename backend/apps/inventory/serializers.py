from rest_framework import serializers
from .models import (
    Stock,
    StockMovement,
    Batch,
    ProductPolicy,
    InventoryAlert,
    StockMovementBatch,
)


class StockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = Stock
        fields = [
            "id",
            "product",
            "product_name",
            "warehouse_name",
            "warehouse",
            "quantity_on_hand",
            "status",
            "last_updated",
            "created_at",
        ]

        read_only_fields = ["id", "status", "last_updated", "created_at"]


class BatchSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = Batch
        fields = [
            "id",
            "product",
            "product_name",
            "warehouse",
            "warehouse_name",
            "batch_number",
            "quantity",
            "manufacture_date",
            "expiry_date",
            "rework_consumed",
            "created_at",
        ]

        read_only_fields = ["id", "created_at", "batch_number"]


class StockMovementBatchSerializer(serializers.ModelSerializer):
    batch = BatchSerializer(read_only=True)

    class Meta:
        model = StockMovementBatch
        fields = ["batch", "quantity"]


class StockMovementSerializer(serializers.ModelSerializer):
    batches_detail = StockMovementBatchSerializer(
        source="stockmovementbatch_set", many=True, read_only=True
    )

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "warehouse",
            "movement_type",
            "total_quantity",
            "reference_number",
            "notes",
            "created_at",
            "batches_detail",
        ]

        read_only_fields = ["id", "created_at", "batches_detail"]


class ProductReorderPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductPolicy
        fields = [
            "id",
            "product",
            "warehouse",
            "min_stock_level",
            "reorder_qty",
            "lead_time_days",
            "retrieval_method",
            "safety_stock_qty",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class InventoryAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryAlert
        fields = [
            "id",
            "product",
            "warehouse",
            "reorder_policy",
            "alert_type",
            "message",
            "status",
            "current_quantity",
            "triggered_by",
            "acknowledged_at",
            "acknowledged_by",
            "created_at",
            "resolved_at",
            "resolved_by",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "message",
            "triggered_by",
            "current_quantity",
        ]


class InventoryBatchExpirySummarySerializer(serializers.Serializer):
    count = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2)


class InventoryBatchesExpiringSerializer(serializers.Serializer):
    within_7_days = InventoryBatchExpirySummarySerializer()
    within_14_days = InventoryBatchExpirySummarySerializer()
    within_30_days = InventoryBatchExpirySummarySerializer()


class InventoryLowStockProductSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    sku = serializers.CharField()
    product_name = serializers.CharField()
    warehouse_id = serializers.UUIDField()
    warehouse_name = serializers.CharField()
    quantity_on_hand = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.ChoiceField(choices=["EMPTY", "ALMOST_OUT", "GOOD", "FULL"])
    min_stock_level = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True
    )
    reorder_qty = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True
    )


class InventoryProductWithoutPolicySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    sku = serializers.CharField()
    name = serializers.CharField()
    category = serializers.CharField(allow_null=True, allow_blank=True)
    unit_of_measure = serializers.CharField(allow_null=True, allow_blank=True)


class InventoryProductsWithoutPolicySerializer(serializers.Serializer):
    count = serializers.IntegerField()
    products = InventoryProductWithoutPolicySerializer(many=True)


class InventoryOverviewSummarySerializer(serializers.Serializer):
    as_of_date = serializers.DateField()
    warehouse_id = serializers.UUIDField(allow_null=True, required=False)
    total_active_products = serializers.IntegerField()
    total_warehouses = serializers.IntegerField()
    stock_status_counts = serializers.DictField(child=serializers.IntegerField())
    open_alert_counts_by_type = serializers.DictField(child=serializers.IntegerField())
    batches_expiring = InventoryBatchesExpiringSerializer()
    expired_batches_with_quantity = InventoryBatchExpirySummarySerializer()
    stock_movement_counts_by_type = serializers.DictField(
        child=serializers.IntegerField()
    )
    top_low_stock_products = InventoryLowStockProductSerializer(many=True)
    products_without_active_reorder_policy = (
        InventoryProductsWithoutPolicySerializer()
    )


class InventoryMovementTrendRowSerializer(serializers.Serializer):
    period = serializers.DateTimeField()
    count = serializers.IntegerField()
    total_quantity = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )


class InventoryMovementTrendsSerializer(serializers.Serializer):
    date_from = serializers.DateField(allow_null=True, required=False)
    date_to = serializers.DateField(allow_null=True, required=False)
    warehouse_id = serializers.UUIDField(allow_null=True, required=False)
    interval = serializers.ChoiceField(choices=["day", "week", "month"])
    inbound = InventoryMovementTrendRowSerializer(many=True)
    outbound = InventoryMovementTrendRowSerializer(many=True)
    adjustments = InventoryMovementTrendRowSerializer(many=True)
    returns = InventoryMovementTrendRowSerializer(many=True)
