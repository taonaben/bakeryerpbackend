from rest_framework import serializers


class PurchasingOverduePOSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    value = serializers.DecimalField(max_digits=14, decimal_places=2)


class PurchasingPendingApprovalsSerializer(serializers.Serializer):
    submitted_prs = serializers.IntegerField()
    submitted_pos = serializers.IntegerField()
    draft_grns = serializers.IntegerField()
    draft_supplier_invoices = serializers.IntegerField()


class PurchasingSupplierRiskSerializer(serializers.Serializer):
    suppliers_on_hold = serializers.IntegerField()
    inactive_suppliers = serializers.IntegerField()
    expired_documents = serializers.IntegerField()
    expiring_documents = serializers.IntegerField()
    expiring_within_days = serializers.IntegerField()


class PurchasingMatchExceptionsSerializer(serializers.Serializer):
    price_variance_lines = serializers.IntegerField()
    quantity_variance_lines = serializers.IntegerField()
    unmatched_lines = serializers.IntegerField()
    invoices_with_exceptions = serializers.IntegerField()
    checked_invoices = serializers.IntegerField()


class PurchasingOverviewSummarySerializer(serializers.Serializer):
    as_of_date = serializers.DateField()
    warehouse_id = serializers.UUIDField(allow_null=True, required=False)
    pr_counts_by_status = serializers.DictField(child=serializers.IntegerField())
    po_counts_by_status = serializers.DictField(child=serializers.IntegerField())
    open_po_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    overdue_pos = PurchasingOverduePOSerializer()
    grn_counts_by_status = serializers.DictField(child=serializers.IntegerField())
    supplier_invoice_counts_by_status = serializers.DictField(
        child=serializers.IntegerField()
    )
    pending_approvals = PurchasingPendingApprovalsSerializer()
    supplier_risk = PurchasingSupplierRiskSerializer()
    match_exceptions = PurchasingMatchExceptionsSerializer()


class PurchasingTrendRowSerializer(serializers.Serializer):
    period = serializers.DateField()
    count = serializers.IntegerField(required=False)
    total_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )


class PurchasingOverviewTrendsSerializer(serializers.Serializer):
    date_from = serializers.DateField(allow_null=True, required=False)
    date_to = serializers.DateField(allow_null=True, required=False)
    warehouse_id = serializers.UUIDField(allow_null=True, required=False)
    interval = serializers.ChoiceField(choices=["day", "week", "month"])
    po_value = PurchasingTrendRowSerializer(many=True)
    grns_approved = PurchasingTrendRowSerializer(many=True)
    supplier_invoices_approved = PurchasingTrendRowSerializer(many=True)
    supplier_invoices_paid = PurchasingTrendRowSerializer(many=True)
    overdue_pos = PurchasingTrendRowSerializer(many=True)


class PurchasingSupplierPerformanceRowSerializer(serializers.Serializer):
    supplier_id = serializers.UUIDField()
    supplier_name = serializers.CharField()
    rating = serializers.IntegerField(allow_null=True)
    on_hold = serializers.BooleanField()
    is_active = serializers.BooleanField()
    total_grns = serializers.IntegerField()
    approved_grns = serializers.IntegerField()
    rejected_grns = serializers.IntegerField()
    on_time_delivery_rate = serializers.FloatField(allow_null=True)
    average_lead_time_days = serializers.FloatField(allow_null=True)
    price_variance_lines = serializers.IntegerField()
    quantity_variance_lines = serializers.IntegerField()
    unmatched_lines = serializers.IntegerField()
    invoices_with_exceptions = serializers.IntegerField()
    total_exception_lines = serializers.IntegerField()


class PurchasingSupplierPerformanceSerializer(serializers.Serializer):
    date_from = serializers.DateField(allow_null=True, required=False)
    date_to = serializers.DateField(allow_null=True, required=False)
    supplier_id = serializers.UUIDField(allow_null=True, required=False)
    suppliers = PurchasingSupplierPerformanceRowSerializer(many=True)
    best_suppliers = PurchasingSupplierPerformanceRowSerializer(many=True)
    worst_suppliers = PurchasingSupplierPerformanceRowSerializer(many=True)
