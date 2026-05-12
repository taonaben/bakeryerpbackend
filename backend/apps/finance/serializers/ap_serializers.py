from rest_framework import serializers
from apps.finance.models import AccountsPayable, SupplierPayment


class SupplierPaymentSerializer(serializers.ModelSerializer):
    entry_number = serializers.CharField(
        source="journal_entry.entry_number", read_only=True
    )
    bank_account_name = serializers.CharField(
        source="bank_account.name", read_only=True
    )

    class Meta:
        model = SupplierPayment
        fields = [
            "id",
            "accounts_payable",
            "amount",
            "payment_date",
            "payment_method",
            "bank_account",
            "bank_account_name",
            "reference",
            "journal_entry",
            "entry_number",
            "paid_by",
            "notes",
            "created_at",
        ]
        read_only_fields = fields


class APSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    invoice_number = serializers.CharField(
        source="supplier_invoice.invoice_number", read_only=True
    )
    entry_number = serializers.CharField(
        source="journal_entry.entry_number", read_only=True
    )
    payments = SupplierPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = AccountsPayable
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "supplier_invoice",
            "invoice_number",
            "original_amount",
            "amount_paid",
            "amount_outstanding",
            "due_date",
            "status",
            "journal_entry",
            "entry_number",
            "created_at",
            "updated_at",
            "payments",
        ]
        read_only_fields = fields


class RecordSupplierPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=0.01,
        help_text="Payment amount to apply against this payable.",
    )
    payment_method = serializers.ChoiceField(
        choices=["cash", "bank_transfer", "cheque", "mobile_money"],
        help_text="How the supplier is being paid.",
    )
    bank_account = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text=(
            "Optional bank/cash account id. If omitted, the default BANK account is used."
        ),
    )
    reference = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional external payment reference (transaction id, cheque no.).",
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional internal note for finance audit trail.",
    )
