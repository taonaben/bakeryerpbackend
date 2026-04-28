from rest_framework import serializers
from apps.sales.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "invoice", "invoice_number", "customer", "customer_name",
                  "amount", "payment_method", "payment_date", "reference",
                  "received_by", "notes"]
        read_only_fields = ["id", "customer", "payment_date", "received_by"]


class RecordPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)
    payment_method = serializers.ChoiceField(
        choices=["cash", "bank_transfer", "mobile_money", "cheque"]
    )
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    allow_overpayment = serializers.BooleanField(required=False, default=False)
