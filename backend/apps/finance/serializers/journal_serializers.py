from rest_framework import serializers
from apps.accounting.models import JournalEntry, JournalEntryLine


class JournalEntryLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = JournalEntryLine
        fields = ["id", "account", "account_code", "account_name",
                  "type", "amount", "description"]
        read_only_fields = fields


class JournalEntryListSerializer(serializers.ModelSerializer):
    fiscal_period_name = serializers.CharField(source="fiscal_period.name", read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            "id", "entry_number", "entry_date", "entry_type",
            "fiscal_period", "fiscal_period_name",
            "reference_type", "reference_id",
            "description", "is_balanced", "is_reversed", "created_at",
        ]
        read_only_fields = fields


class JournalEntryDetailSerializer(serializers.ModelSerializer):
    fiscal_period_name = serializers.CharField(source="fiscal_period.name", read_only=True)
    lines = JournalEntryLineSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            "id", "entry_number", "entry_date", "entry_type",
            "fiscal_period", "fiscal_period_name",
            "reference_type", "reference_id",
            "description", "is_balanced", "is_reversed",
            "reversed_by", "created_by", "created_at", "lines",
        ]
        read_only_fields = fields


class ManualJournalLineInputSerializer(serializers.Serializer):
    account_code = serializers.CharField()
    type = serializers.ChoiceField(choices=["debit", "credit"])
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)
    description = serializers.CharField(required=False, allow_blank=True, default="")


class ManualJournalEntrySerializer(serializers.Serializer):
    entry_date = serializers.DateField()
    description = serializers.CharField()
    lines = ManualJournalLineInputSerializer(many=True, min_length=2)

    def validate_lines(self, lines):
        debits = sum(l["amount"] for l in lines if l["type"] == "debit")
        credits = sum(l["amount"] for l in lines if l["type"] == "credit")
        if debits != credits:
            raise serializers.ValidationError(
                f"Entry is unbalanced: debits={debits}, credits={credits}."
            )
        return lines


class ReverseJournalSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
