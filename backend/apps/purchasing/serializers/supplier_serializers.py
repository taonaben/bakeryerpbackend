from rest_framework import serializers

from apps.purchasing.models import Supplier, SupplierProduct


class SupplierSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = Supplier
        fields = [
            "id",
            "company",
            "company_name",
            "name",
            "contact_person",
            "email",
            "phone_number",
            "address",
            "payment_terms",
            "currency",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_active", "created_at", "updated_at"]


class SupplierCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "company",
            "name",
            "contact_person",
            "email",
            "phone_number",
            "address",
            "payment_terms",
            "currency",
        ]


class SupplierProductSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = SupplierProduct
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "product",
            "product_name",
            "price",
            "lead_time_days",
            "is_preferred",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SupplierProductCreateSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    lead_time_days = serializers.IntegerField(min_value=0)
    is_preferred = serializers.BooleanField(default=False)
