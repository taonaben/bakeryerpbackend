from rest_framework import serializers

from apps.formulation.serializers import FormulaSerializer
from .models import ProductionOrder


class ProductionPlanSerializer(serializers.Serializer):
    scale_factor = serializers.DecimalField(max_digits=18, decimal_places=6)
    formula = FormulaSerializer(read_only=True)
    shortages = serializers.DictField(child=serializers.DictField(), read_only=True)
    validation_errors = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    can_run = serializers.BooleanField(read_only=True)


class ProductionOrderSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = ProductionOrder
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "status",
            "scheduled_start",
            "scheduled_end",
            "warehouse",
            "warehouse_name",
            "formula",
        ]

        read_only_fields = ["id", "status"]
