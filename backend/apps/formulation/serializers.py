from rest_framework import serializers

from central.models import Product

from .models import Formula, FormulaLine


class FormulaLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = FormulaLine
        fields = [
            "id",
            "formula",
            "sequence",
            "line_type",
            "product",
            "product_name",
            "quantity",
            "text",
        ]
        read_only_fields = ["id"]


class FormulaLineWriteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=False,
        allow_null=True,
    )
    quantity = serializers.FloatField(required=False, allow_null=True)
    text = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = FormulaLine
        fields = [
            "id",
            "sequence",
            "line_type",
            "product",
            "quantity",
            "text",
        ]

    def validate(self, attrs):
        line_type = attrs.get("line_type")
        product = attrs.get("product")
        quantity = attrs.get("quantity")
        text = attrs.get("text")

        if line_type in {"MATERIAL", "BYPRODUCT"} and not product:
            raise serializers.ValidationError(
                {"product": "This field is required for material and byproduct lines."}
            )

        if line_type in {"MATERIAL", "BYPRODUCT"} and quantity is None:
            raise serializers.ValidationError(
                {"quantity": "This field is required for material and byproduct lines."}
            )

        if line_type in {"TEXT", "INSTRUCTION", "PROCESS"} and not text:
            raise serializers.ValidationError(
                {"text": "This field is required for text, instruction, and process lines."}
            )

        return attrs


class FormulaSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    lines = FormulaLineSerializer(many=True, read_only=True)

    class Meta:
        model = Formula
        fields = [
            "id",
            "name",
            "product",
            "product_name",
            "revision",
            "batch_size",
            "yield_percentage",
            "status",
            "is_active",
            "on_hold",
            "on_hold_reason",
            "created_at",
            "lines",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "on_hold",
            "on_hold_reason",
            "lines",
        ]


class FormulaWriteSerializer(serializers.ModelSerializer):
    lines = FormulaLineWriteSerializer(many=True, allow_empty=False, required=False)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = Formula
        fields = [
            "name",
            "product",
            "revision",
            "batch_size",
            "yield_percentage",
            "status",
            "is_active",
            "lines",
        ]
        extra_kwargs = {
            "status": {"required": False},
            "is_active": {"required": False},
        }

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("At least one line is required.")

        sequences = [line["sequence"] for line in value]
        if len(sequences) != len(set(sequences)):
            raise serializers.ValidationError("Line sequence values must be unique.")

        line_ids = [str(line["id"]) for line in value if line.get("id")]
        if len(line_ids) != len(set(line_ids)):
            raise serializers.ValidationError("Duplicate line ids are not allowed.")

        return value

    def validate(self, attrs):
        request = self.context.get("request")
        product = attrs.get("product")
        lines = attrs.get("lines")

        if self.instance is None and lines is None:
            raise serializers.ValidationError({"lines": "This field is required."})

        if request and product and product.company_id != getattr(
            request.user, "company_id", None
        ):
            raise serializers.ValidationError(
                {"product": "Selected product does not belong to your company."}
            )

        if request and lines:
            company_id = getattr(request.user, "company_id", None)
            invalid_products = [
                str(line["product"].id)
                for line in lines
                if line.get("product") and line["product"].company_id != company_id
            ]
            if invalid_products:
                raise serializers.ValidationError(
                    {
                        "lines": (
                            "One or more line products do not belong to your company."
                        )
                    }
                )

        return attrs

    def create(self, validated_data):
        from .services.formula_services import FormulaService

        return FormulaService.create_with_lines(validated_data)

    def update(self, instance, validated_data):
        from .services.formula_services import FormulaService

        return FormulaService.update_with_lines(instance, validated_data)


class FormulaHoldSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
