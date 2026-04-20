from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.purchasing.models import (
    PurchaseOrder,
    PurchaseOrderLineItem,
)

User = get_user_model()


class PurchaseOrderLineItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = PurchaseOrderLineItem
        fields = [
            "id",
            "purchase_order",
            "product",
            "product_name",
            "quantity",
            "unit_of_measure",
            "unit_price",
            "total_price",
            "quantity_received",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "total_price",
            "quantity_received",
            "created_at",
            "updated_at",
        ]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    line_items = PurchaseOrderLineItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(source="line_items.count", read_only=True)
    pr_number = serializers.CharField(source="purchase_requisition.pr_number", read_only=True)
    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "po_number",
            "supplier",
            "supplier_name",
            "warehouse",
            "warehouse_name",
            "purchase_requisition",
            "pr_number",
            "created_by",
            "order_date",
            "expected_delivery_date",
            "currency",
            "description",
            "total_amount",
            "status",
            "submitted_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "cancelled_by",
            "cancelled_at",
            "created_at",
            "updated_at",
            "item_count",
            "line_items",
        ]
        read_only_fields = [
            "id",
            "po_number",
            "created_by",
            "order_date",
            "total_amount",
            "status",
            "submitted_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "cancelled_by",
            "cancelled_at",
            "created_at",
            "updated_at",
            "item_count",
            "line_items",
        ]


class PurchaseOrderCreateLineSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = serializers.CharField(required=False, allow_blank=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    description = serializers.CharField(required=False, allow_blank=True)


class PurchaseOrderCreateSerializer(serializers.Serializer):
    supplier_id = serializers.UUIDField()
    warehouse_id = serializers.UUIDField()
    purchase_requisition_id = serializers.UUIDField(required=False, allow_null=True)
    currency = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    expected_delivery_date = serializers.DateField(required=False, allow_null=True)
    lines = PurchaseOrderCreateLineSerializer(many=True)


class PurchaseOrderSubmitSerializer(serializers.Serializer):
    submitted_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class PurchaseOrderApproveSerializer(serializers.Serializer):
    approved_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class PurchaseOrderRejectSerializer(serializers.Serializer):
    rejected_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    reason = serializers.CharField(required=False, allow_blank=True)


class PurchaseOrderCancelSerializer(serializers.Serializer):
    cancelled_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

