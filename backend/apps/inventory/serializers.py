from rest_framework import serializers
from .models import Stock, StockMovement, Batch, ProductReorderPolicy, InventoryAlert


class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = [
            "id",
            "product",
            "warehouse",
            "quantity_on_hand",
            "status",
            "last_updated",
            "created_at",
        ]
        
        read_only_fields = ["id", "status", "last_updated", "created_at"]

class BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = [
            "id",
            "product",
            "warehouse",
            "batch_number",
            "quantity",
            "manufacture_date",
            "expiry_date",
            "created_at",
        ]
        
        read_only_fields = ["id", "created_at", "batch_number"]
        
class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = [
            "id",
            "batch",
            "movement_type",
            "quantity",
            "reference_number",
            "notes",
            "created_at",
        ]
        
        read_only_fields = ["id", "created_at"]
        
        
class ProductReorderPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReorderPolicy
        fields = [
            "id",
            "product",
            "warehouse",
            "min_stock_level",
            "reorder_qty",
            "lead_time_days",
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
        read_only_fields = ["id", "created_at", "message", "triggered_by", "current_quantity"]