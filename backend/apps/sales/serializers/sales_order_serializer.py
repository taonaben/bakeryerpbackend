from rest_framework import serializers
from apps.sales.models import SalesOrder, SalesOrderLine


class SalesOrderLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = SalesOrderLine
        fields = ["id", "product", "product_name", "quantity", "unit_price",
                  "subtotal", "quantity_dispatched", "cost_per_unit", "cogs_total"]
        read_only_fields = ["id", "unit_price", "subtotal", "quantity_dispatched",
                            "cost_per_unit", "cogs_total"]


class SalesOrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = SalesOrder
        fields = ["id", "order_number", "customer", "customer_name", "warehouse",
                  "warehouse_name", "order_type", "status", "order_date",
                  "total_amount", "created_at"]
        read_only_fields = fields


class SalesOrderDetailSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    lines = SalesOrderLineSerializer(many=True, read_only=True)

    class Meta:
        model = SalesOrder
        fields = ["id", "order_number", "customer", "customer_name", "warehouse",
                  "warehouse_name", "order_type", "status", "order_date",
                  "expected_delivery_date", "delivery_address", "notes",
                  "subtotal", "tax_amount", "total_amount", "created_by",
                  "created_at", "updated_at", "lines"]
        read_only_fields = ["id", "order_number", "order_type", "status", "subtotal",
                            "tax_amount", "total_amount", "created_by", "created_at", "updated_at"]


class SalesOrderCreateSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    warehouse_id = serializers.UUIDField()
    expected_delivery_date = serializers.DateField(required=False, allow_null=True)
    delivery_address = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class SalesOrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesOrder
        fields = ["notes", "delivery_address", "expected_delivery_date"]


class AddLineSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)


class UpdateLineSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)


class CancelOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class POSLineSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)


class POSSaleSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField(required=False)
    warehouse_id = serializers.UUIDField()
    lines = POSLineSerializer(many=True, min_length=1)
    payment_method = serializers.ChoiceField(
        choices=["cash", "bank_transfer", "mobile_money", "cheque"],
        default="cash",
    )
