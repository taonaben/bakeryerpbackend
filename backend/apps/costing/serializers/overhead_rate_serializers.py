from rest_framework import serializers
from apps.costing.models import OverheadRate


class OverheadRateSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)

    class Meta:
        model = OverheadRate
        fields = [
            "id",
            "warehouse",
            "warehouse_name",
            "period_start",
            "period_end",
            "total_overhead_budgeted",
            "planned_production_units",
            "rate_per_unit",
            "currency",
            "notes",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "rate_per_unit", "created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("period_start")
        end = attrs.get("period_end")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"period_end": "period_end must be on or after period_start."}
            )
        units = attrs.get("planned_production_units")
        if units is not None and units <= 0:
            raise serializers.ValidationError(
                {"planned_production_units": "planned_production_units must be greater than zero."}
            )
        return attrs

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
