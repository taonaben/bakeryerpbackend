from rest_framework import serializers
from apps.accounting.models import FiscalPeriod


class FiscalPeriodSerializer(serializers.ModelSerializer):
    closed_by_name = serializers.CharField(source="closed_by.get_full_name", read_only=True)

    class Meta:
        model = FiscalPeriod
        fields = [
            "id", "name", "period_start", "period_end",
            "status", "closed_at", "closed_by", "closed_by_name", "created_at",
        ]
        read_only_fields = ["id", "status", "closed_at", "closed_by", "created_at"]


class FiscalPeriodCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    period_start = serializers.DateField()
    period_end = serializers.DateField()

    def validate(self, data):
        if data["period_end"] < data["period_start"]:
            raise serializers.ValidationError("period_end must be on or after period_start.")
        return data
