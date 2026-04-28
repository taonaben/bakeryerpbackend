from rest_framework import serializers


class DailySummarySerializer(serializers.Serializer):
    date = serializers.DateField()
    warehouse_id = serializers.UUIDField(allow_null=True)
    warehouse_name = serializers.CharField(allow_null=True)
    total_transactions = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_cogs = serializers.DecimalField(max_digits=14, decimal_places=2)
    gross_profit = serializers.DecimalField(max_digits=14, decimal_places=2)


class RevenueByProductSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    total_quantity_sold = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)


class MarginByProductSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_cogs = serializers.DecimalField(max_digits=14, decimal_places=2)
    gross_profit = serializers.DecimalField(max_digits=14, decimal_places=2)
    margin_percentage = serializers.DecimalField(
        max_digits=7, decimal_places=2, allow_null=True
    )


class CustomerStatementSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    customer_name = serializers.CharField()
    total_ordered = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_invoiced = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=14, decimal_places=2)
    outstanding_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    orders = serializers.ListField(child=serializers.DictField())
    invoices = serializers.ListField(child=serializers.DictField())
    payments = serializers.ListField(child=serializers.DictField())


class OutstandingDebtorSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    customer_name = serializers.CharField()
    company_name = serializers.CharField(allow_null=True)
    outstanding_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    oldest_due_date = serializers.DateField(allow_null=True)
    days_overdue = serializers.IntegerField(allow_null=True)


class SalesByWarehouseSerializer(serializers.Serializer):
    warehouse_id = serializers.UUIDField()
    warehouse_name = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_cogs = serializers.DecimalField(max_digits=14, decimal_places=2)
    gross_profit = serializers.DecimalField(max_digits=14, decimal_places=2)
