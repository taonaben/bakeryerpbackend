from rest_framework import serializers
from apps.sales.models import Customer, CustomerProduct
from central.models import Product


class CustomerListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "customer_type", "name", "phone", "email", "company_name",
                  "payment_terms", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class CustomerDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "customer_type", "name", "phone", "email", "address",
                  "company_name", "payment_terms", "credit_limit", "tax_number",
                  "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class CustomerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["customer_type", "name", "phone", "email", "address",
                  "company_name", "payment_terms", "credit_limit", "tax_number"]

    def validate(self, data):
        if data.get("customer_type") == "business" and not data.get("payment_terms"):
            raise serializers.ValidationError(
                {"payment_terms": "payment_terms is required for business customers."}
            )
        return data


class CustomerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["name", "phone", "email", "address", "company_name",
                  "payment_terms", "credit_limit", "tax_number", "is_active"]


class CustomerOutstandingSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    customer_name = serializers.CharField()
    credit_limit = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    outstanding_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    available_credit = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    over_limit = serializers.BooleanField()


class CustomerProductSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = CustomerProduct
        fields = ["id", "customer", "product", "product_name", "unit_price",
                  "min_order_quantity", "is_active", "valid_from", "valid_until", "created_at"]
        read_only_fields = ["id", "customer", "created_at"]


class CustomerProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProduct
        fields = ["product", "unit_price", "min_order_quantity", "valid_from", "valid_until"]


class CustomerProductUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProduct
        fields = ["unit_price", "min_order_quantity", "is_active", "valid_from", "valid_until"]
