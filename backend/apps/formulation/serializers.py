from rest_framework import serializers
from .models import Formula, FormulaLine


class FormulaLineSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = FormulaLine
        fields = [
            "id",
            "material_name",
            "formula",
            "sequence",
            "line_type",
            "product",
            "quantity",
            "text",
        ]
        read_only_fields = ["id"]


class FormulaLineCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormulaLine
        fields = [
            "sequence",
            "line_type",
            "product",
            "quantity",
            "text",
        ]


class FormulaSerializer(serializers.ModelSerializer):
    lines = FormulaLineSerializer(many=True, read_only=True)

    class Meta:
        model = Formula
        fields = [
            "id",
            "name",
            "product",
            "revision",
            "batch_size",
            "yield_percentage",
            "status",
            "created_at",
            "lines",
        ]
        read_only_fields = ["id", "created_at", "lines"]


class FormulaCreateSerializer(serializers.ModelSerializer):
    lines = FormulaLineCreateSerializer(many=True, allow_empty=False)

    class Meta:
        model = Formula
        fields = [
            "name",
            "product",
            "revision",
            "batch_size",
            "yield_percentage",
            "status",
            "lines",
        ]
        extra_kwargs = {
            "status": {"required": False},
        }

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("At least one line is required.")
        return value

    def create(self, validated_data):
        from .services.formula_services import FormulaService

        return FormulaService.create_with_lines(validated_data)
