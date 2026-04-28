from rest_framework import serializers
from apps.finance.models import AccountsPayable, SupplierPayment


class SupplierPaymentSerializer(serializers.ModelSerializer):
    entry_number = serializers.CharField(source="journal_entry.entry_number", read_only=True)

    class Meta:
        model = SupplierPayment
        fields = [
            "id", "accounts_payable", "amount", "payment_date",
            "payment_method", "reference", "journal_entry", "entry_number",
            "paid_by", "notes", "created_at",
        ]
        read_only_fields = fields


class APSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    invoice_number = serializers.CharField(
        source="supplier_invoice.invoice_number", read_only=True
    )
    entry_number = serializers.CharField(source="journal_entry.entry_number", read_only=True)
    payments = SupplierPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = AccountsPayable
        fields = [
            "id", "supplier", "supplier_name", "supplier_invoice", "invoice_number",
            "original_amount", "amount_paid", "amount_outstanding",
            "due_date", "status", "journal_entry", "entry_number",
            "created_at", "updated_at", "payments",
        ]
        read_only_fields = fields


class RecordSupplierPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)
    payment_method = serializers.ChoiceField(
        choices=["cash", "bank_transfer", "cheque", "mobile_money"]
    )
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
