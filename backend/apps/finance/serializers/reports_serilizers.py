from rest_framework import serializers


class TrialBalanceLineSerializer(serializers.Serializer):
    account_code = serializers.CharField()
    account_name = serializers.CharField()
    account_type = serializers.CharField()
    account_subtype = serializers.CharField()
    total_debits = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_credits = serializers.DecimalField(max_digits=14, decimal_places=2)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    normal_balance = serializers.CharField()


class TrialBalanceSerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    fiscal_period = serializers.CharField(allow_null=True)
    total_debits = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_credits = serializers.DecimalField(max_digits=14, decimal_places=2)
    is_balanced = serializers.BooleanField()
    lines = TrialBalanceLineSerializer(many=True)


class IncomeStatementLineSerializer(serializers.Serializer):
    account_code = serializers.CharField()
    account_name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class IncomeStatementSerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    revenue = IncomeStatementLineSerializer(many=True)
    cost_of_sales = IncomeStatementLineSerializer(many=True)
    operating_expenses = IncomeStatementLineSerializer(many=True)
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_cost_of_sales = serializers.DecimalField(max_digits=14, decimal_places=2)
    gross_profit = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_operating_expenses = serializers.DecimalField(max_digits=14, decimal_places=2)
    net_profit = serializers.DecimalField(max_digits=14, decimal_places=2)


class BalanceSheetSectionSerializer(serializers.Serializer):
    account_code = serializers.CharField()
    account_name = serializers.CharField()
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)


class BalanceSheetSerializer(serializers.Serializer):
    as_of_date = serializers.DateField()
    assets = BalanceSheetSectionSerializer(many=True)
    liabilities = BalanceSheetSectionSerializer(many=True)
    equity = BalanceSheetSectionSerializer(many=True)
    total_assets = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_liabilities = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_equity = serializers.DecimalField(max_digits=14, decimal_places=2)
    is_balanced = serializers.BooleanField()


class AgingBucketSerializer(serializers.Serializer):
    name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    count = serializers.IntegerField()


class ARAgingRowSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    customer_name = serializers.CharField()
    current = serializers.DecimalField(max_digits=14, decimal_places=2)
    days_1_30 = serializers.DecimalField(max_digits=14, decimal_places=2)
    days_31_60 = serializers.DecimalField(max_digits=14, decimal_places=2)
    days_61_90 = serializers.DecimalField(max_digits=14, decimal_places=2)
    over_90 = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_outstanding = serializers.DecimalField(max_digits=14, decimal_places=2)


class APAgingRowSerializer(serializers.Serializer):
    supplier_id = serializers.UUIDField()
    supplier_name = serializers.CharField()
    current = serializers.DecimalField(max_digits=14, decimal_places=2)
    days_1_30 = serializers.DecimalField(max_digits=14, decimal_places=2)
    days_31_60 = serializers.DecimalField(max_digits=14, decimal_places=2)
    days_61_90 = serializers.DecimalField(max_digits=14, decimal_places=2)
    over_90 = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_outstanding = serializers.DecimalField(max_digits=14, decimal_places=2)
