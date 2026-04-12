from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.purchasing.models import SupplierInvoice, SupplierInvoiceLineItem

User = get_user_model()


class SupplierInvoiceLineItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = SupplierInvoiceLineItem
        fields = [
            "id",
            "supplier_invoice",
            "gr_line_item",
            "product",
            "product_name",
            "quantity_invoiced",
            "unit_of_measure",
            "unit_price",
            "total_price",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "total_price", "created_at", "updated_at"]


class SupplierInvoiceSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    po_number = serializers.CharField(source="purchase_order.po_number", read_only=True)
    line_items = SupplierInvoiceLineItemSerializer(many=True, read_only=True)

    class Meta:
        model = SupplierInvoice
        fields = [
            "id",
            "invoice_number",
            "purchase_order",
            "po_number",
            "supplier",
            "supplier_name",
            "warehouse",
            "warehouse_name",
            "invoice_date",
            "due_date",
            "total_amount",
            "status",
            "description",
            "approved_by",
            "rejected_by",
            "rejection_reason",
            "paid_by",
            "payment_reference",
            "created_at",
            "updated_at",
            "line_items",
        ]
        read_only_fields = [
            "id",
            "invoice_number",
            "total_amount",
            "status",
            "approved_by",
            "rejected_by",
            "rejection_reason",
            "paid_by",
            "payment_reference",
            "created_at",
            "updated_at",
            "line_items",
        ]


# --- Action serializers ---


class InvoiceCreateLineSerializer(serializers.Serializer):
    gr_line_item_id = serializers.UUIDField(required=False, allow_null=True)
    product_id = serializers.UUIDField()
    quantity_invoiced = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = serializers.CharField(required=False, allow_blank=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    description = serializers.CharField(required=False, allow_blank=True)


class InvoiceCreateSerializer(serializers.Serializer):
    po_id = serializers.UUIDField()
    supplier_id = serializers.UUIDField()
    invoice_date = serializers.DateField()
    due_date = serializers.DateField(required=False, allow_null=True)
    lines = InvoiceCreateLineSerializer(many=True)


class InvoiceApproveSerializer(serializers.Serializer):
    approved_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class InvoiceRejectSerializer(serializers.Serializer):
    rejected_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    reason = serializers.CharField(required=False, allow_blank=True)


class InvoiceMarkPaidSerializer(serializers.Serializer):
    paid_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    payment_reference = serializers.CharField(required=False, allow_blank=True)


class MatchResultLineSerializer(serializers.Serializer):
    invoice_line_id = serializers.CharField()
    product_id = serializers.CharField()
    product_name = serializers.CharField()
    invoice_qty = serializers.DecimalField(max_digits=10, decimal_places=2)
    invoice_unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    gr_qty = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    gr_unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )
    po_qty = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    po_unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )
    reason = serializers.CharField(required=False)
    price_diff_po = serializers.FloatField(required=False)
    price_diff_gr = serializers.FloatField(required=False)
    qty_diff_gr = serializers.FloatField(required=False)


class MatchResultSerializer(serializers.Serializer):
    matched = MatchResultLineSerializer(many=True)
    price_variance = MatchResultLineSerializer(many=True)
    qty_variance = MatchResultLineSerializer(many=True)
    unmatched = MatchResultLineSerializer(many=True)
