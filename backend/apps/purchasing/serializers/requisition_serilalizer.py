from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.purchasing.models import PurchaseRequisition, PurchaseRequisitionLineItem

User = get_user_model()


class PurchaseRequisitionLineItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = PurchaseRequisitionLineItem
        fields = [
            "id",
            "purchase_requisition",
            "product",
            "product_name",
            "quantity",
            "unit_of_measure",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PurchaseRequisitionSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(
        source="requested_by.username", read_only=True
    )
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    line_items = PurchaseRequisitionLineItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseRequisition
        fields = [
            "id",
            "pr_number",
            "requested_by",
            "requested_by_name",
            "warehouse",
            "warehouse_name",
            "title",
            "description",
            "status",
            "submitted_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "converted_at",
            "created_at",
            "updated_at",
            "line_items",
        ]
        read_only_fields = [
            "id",
            "pr_number",
            "requested_by",
            "status",
            "submitted_by",
            "submitted_at",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "converted_at",
            "created_at",
            "updated_at",
            "line_items",
        ]


class PurchaseRequisitionCreateLineSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)


class PurchaseRequisitionCreateSerializer(serializers.Serializer):
    warehouse_id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    lines = PurchaseRequisitionCreateLineSerializer(many=True)


class PurchaseRequisitionSubmitSerializer(serializers.Serializer):
    submitted_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class PurchaseRequisitionApproveSerializer(serializers.Serializer):
    approved_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class PurchaseRequisitionRejectSerializer(serializers.Serializer):
    rejected_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    reason = serializers.CharField(required=False, allow_blank=True)


class PurchaseRequisitionConvertLineSerializer(serializers.Serializer):
    pr_line_item_id = serializers.UUIDField()
    unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )


class PurchaseRequisitionConvertSerializer(serializers.Serializer):
    supplier_id = serializers.UUIDField()
    created_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    lines = PurchaseRequisitionConvertLineSerializer(many=True, required=False)
