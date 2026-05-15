from rest_framework import serializers
from apps.sales.models import Delivery, DeliveryLine


class DeliveryLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)

    class Meta:
        model = DeliveryLine
        fields = ["id", "product", "product_name", "batch", "batch_number", "quantity_delivered"]
        read_only_fields = fields


class DeliveryListSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="sales_order.order_number", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = Delivery
        fields = ["id", "delivery_number", "sales_order", "order_number", "warehouse",
                  "warehouse_name", "status", "dispatched_at", "delivered_at"]
        read_only_fields = fields


class DeliveryDetailSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="sales_order.order_number", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    lines = DeliveryLineSerializer(many=True, read_only=True)

    class Meta:
        model = Delivery
        fields = ["id", "delivery_number", "sales_order", "order_number", "warehouse",
                  "warehouse_name", "status", "dispatched_at", "delivered_at",
                  "driver_name", "vehicle", "notes", "lines"]
        read_only_fields = fields


class ConfirmReceiptSerializer(serializers.Serializer):
    """Body for PATCH /deliveries/{id}/confirm-receipt"""
    notes = serializers.CharField(required=False, allow_blank=True)


class FailDeliverySerializer(serializers.Serializer):
    """Body for PATCH /deliveries/{id}/fail"""
    reason = serializers.CharField()
