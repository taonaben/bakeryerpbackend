from rest_framework import serializers

from apps.formulation.serializers import FormulaSerializer
from .models import ProductionOrder


class ProductionPlanSerializer(serializers.Serializer):
    formula = FormulaSerializer(read_only=True)
    scale_factor = serializers.DecimalField(max_digits=18, decimal_places=6)


class ProductionOrderSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProductionOrder
        fields = [
            "id",
            "product",
            "quantity",
            "status",
            "scheduled_start",
            "scheduled_end",
            "warehouse",
            "formula",
        ]

        read_only_fields = ["id", "status"]
