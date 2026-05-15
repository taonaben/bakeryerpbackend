from rest_framework import serializers
from apps.sales.models import Invoice, SalesOrderLine


class InvoiceLineSerializer(serializers.Serializer):
    """Read-only line breakdown derived from SalesOrderLines."""
    product_id = serializers.UUIDField(source="product.id")
    product_name = serializers.CharField(source="product.name")
    quantity_dispatched = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2)
    line_total = serializers.SerializerMethodField()

    def get_line_total(self, obj):
        return obj.quantity_dispatched * obj.unit_price


class InvoiceListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source="sales_order.customer.name", read_only=True
    )
    order_number = serializers.CharField(source="sales_order.order_number", read_only=True)

    class Meta:
        model = Invoice
        fields = ["id", "invoice_number", "invoice_type", "order_number", "customer_name",
                  "issued_date", "due_date", "total_amount", "status", "created_at"]
        read_only_fields = fields


class InvoiceDetailSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source="sales_order.customer.name", read_only=True
    )
    order_number = serializers.CharField(source="sales_order.order_number", read_only=True)
    lines = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = ["id", "invoice_number", "invoice_type", "sales_order", "order_number",
                  "customer_name", "issued_date", "due_date", "subtotal", "tax_amount",
                  "total_amount", "status", "created_at", "lines"]
        read_only_fields = fields

    def get_lines(self, obj):
        lines = obj.sales_order.lines.select_related("product").all()
        return InvoiceLineSerializer(lines, many=True).data


class CancelInvoiceSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
