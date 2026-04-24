from rest_framework import serializers
from central.models import Product
from apps.costing.models import ProductPricingRule


class ProductPricingRuleSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    updated_by_name = serializers.CharField(source="updated_by.get_full_name", read_only=True)

    class Meta:
        model = ProductPricingRule
        fields = [
            "id",
            "product",
            "product_name",
            "target_gross_margin_percentage",
            "minimum_margin_percentage",
            "standard_cost_reference",
            "recommended_selling_price",
            "minimum_selling_price",
            "currency",
            "last_updated",
            "updated_by",
            "updated_by_name",
        ]
        read_only_fields = [
            "id",
            "standard_cost_reference",
            "recommended_selling_price",
            "minimum_selling_price",
            "last_updated",
            "updated_by",
            "updated_by_name",
        ]


class ProductPricingRuleWriteSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = ProductPricingRule
        fields = [
            "product",
            "target_gross_margin_percentage",
            "minimum_margin_percentage",
            "currency",
        ]

    def validate(self, attrs):
        target = attrs.get("target_gross_margin_percentage")
        minimum = attrs.get("minimum_margin_percentage")
        if target is not None and minimum is not None and minimum > target:
            raise serializers.ValidationError(
                {"minimum_margin_percentage": "Minimum margin cannot exceed target margin."}
            )
        for field, value in [
            ("target_gross_margin_percentage", target),
            ("minimum_margin_percentage", minimum),
        ]:
            if value is not None and (value < 0 or value >= 100):
                raise serializers.ValidationError(
                    {field: "Margin percentage must be between 0 and 99.99."}
                )
        return attrs

    def create(self, validated_data):
        validated_data["updated_by"] = self.context["request"].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data["updated_by"] = self.context["request"].user
        return super().update(instance, validated_data)
