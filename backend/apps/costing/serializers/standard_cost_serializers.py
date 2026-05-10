from rest_framework import serializers
from central.models import Product, Warehouse
from apps.costing.models import StandardCost, StandardCostLine


class StandardCostLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    supplier_name = serializers.CharField(
        source="supplier_product_used.supplier.name", read_only=True
    )

    class Meta:
        model = StandardCostLine
        fields = [
            "id",
            "product",
            "product_name",
            "formula_line",
            "quantity_per_batch",
            "quantity_per_unit",
            "unit_price_used",
            "supplier_product_used",
            "supplier_name",
            "cost_per_unit",
            "cost_percentage",
        ]
        read_only_fields = fields


class StandardCostSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    formula_revision = serializers.IntegerField(source="formula.revision", read_only=True)
    computed_by_name = serializers.CharField(source="computed_by.get_full_name", read_only=True)
    lines = StandardCostLineSerializer(many=True, read_only=True)

    class Meta:
        model = StandardCost
        fields = [
            "id",
            "formula",
            "formula_revision",
            "product",
            "product_name",
            "overhead_rate",
            "material_cost_per_unit",
            "overhead_cost_per_unit",
            "overhead_allocation_method",
            "total_standard_cost_per_unit",
            "batch_size_used",
            "yield_percentage_used",
            "computed_at",
            "computed_by",
            "computed_by_name",
            "currency",
            "lines",
        ]
        read_only_fields = fields


class StandardCostListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views — no nested lines."""
    product_name = serializers.CharField(source="product.name", read_only=True)
    formula_revision = serializers.IntegerField(source="formula.revision", read_only=True)

    class Meta:
        model = StandardCost
        fields = [
            "id",
            "formula",
            "formula_revision",
            "product",
            "product_name",
            "total_standard_cost_per_unit",
            "material_cost_per_unit",
            "overhead_cost_per_unit",
            "overhead_allocation_method",
            "currency",
            "computed_at",
        ]
        read_only_fields = fields


class ComputeStandardCostSerializer(serializers.Serializer):
    """Input for the manual compute trigger endpoint."""
    formula_id = serializers.UUIDField()
    warehouse_id = serializers.UUIDField()

    def validate_formula_id(self, value):
        from apps.formulation.models import Formula
        if not Formula.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Formula not found.")
        return value

    def validate_warehouse_id(self, value):
        if not Warehouse.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Warehouse not found.")
        return value
