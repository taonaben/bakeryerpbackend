from rest_framework import serializers
from apps.finance.models import AccountsReceivable


class ARSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    entry_number = serializers.CharField(source="journal_entry.entry_number", read_only=True)

    class Meta:
        model = AccountsReceivable
        fields = [
            "id", "customer", "customer_name", "invoice", "invoice_number",
            "original_amount", "amount_paid", "amount_outstanding",
            "due_date", "status", "journal_entry", "entry_number",
            "created_at", "updated_at",
        ]
        read_only_fields = fields
