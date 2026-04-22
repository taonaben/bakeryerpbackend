from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.purchasing.models import (
    GoodsReceipt,
    GoodsReceiptLineItem,
)

User = get_user_model()


class GoodsReceiptLineItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = GoodsReceiptLineItem
        fields = [
            "id",
            "goods_receipt",
            "po_line_item",
            "product",
            "product_name",
            "quantity_received",
            "unit_of_measure",
            "supplier_batch_ref",
            "expiry_date",
            "manufacturing_date",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class GoodsReceiptSerializer(serializers.ModelSerializer):
    purchase_order_number = serializers.CharField(
        source="purchase_order.po_number", read_only=True
    )
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    line_items = GoodsReceiptLineItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(source="line_items.count", read_only=True)
    supplier = serializers.SerializerMethodField(read_only=True)
    supplier_name = serializers.SerializerMethodField(read_only=True)
    received_by_name = serializers.CharField(source="received_by.username", read_only=True)

    def get_supplier(self, obj):
        try:
            return obj.purchase_order.supplier.id
        except AttributeError:
            return None

    def get_supplier_name(self, obj):
        try:
            return obj.purchase_order.supplier.name
        except AttributeError:
            return None

    class Meta:
        model = GoodsReceipt
        fields = [
            "id",
            "gr_number",
            "purchase_order",
            "purchase_order_number",
            "supplier",
            "supplier_name",
            "warehouse",
            "warehouse_name",
            "received_date",
            "received_by",
            "received_by_name",
            "status",
            "description",
            "rejection_reason",
            "created_at",
            "updated_at",
            "item_count",
            "line_items",
        ]
        read_only_fields = [
            "id",
            "gr_number",
            "received_date",
            "status",
            "created_at",
            "updated_at",
            "item_count",
            "line_items",
            "received_by_name",
            
        ]


class GoodsReceiptCreateLineSerializer(serializers.Serializer):
    po_line_item_id = serializers.UUIDField()
    quantity_received = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = serializers.CharField(required=False, allow_blank=True)
    supplier_batch_ref = serializers.CharField(required=False, allow_blank=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    manufacturing_date = serializers.DateField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True)


class GoodsReceiptCreateSerializer(serializers.Serializer):
    purchase_order_id = serializers.UUIDField()
    warehouse_id = serializers.UUIDField()
    received_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    lines = GoodsReceiptCreateLineSerializer(many=True)


class GoodsReceiptConfirmSerializer(serializers.Serializer):
    confirmed_by = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )


class GoodsReceiptRejectSerializer(serializers.Serializer):
    rejected_by = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    reason = serializers.CharField(required=False, allow_blank=True)
