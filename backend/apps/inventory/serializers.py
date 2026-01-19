from rest_framework import serializers
from .models import Stock, StockMovement, Batch


class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = [
            "id",
            "product",
            "warehouse",
            "quantity_on_hand",
            "last_updated",
            "created_at",
        ]
        
        read_only_fields = ["id", "last_updated", "created_at"]

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