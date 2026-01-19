from rest_framework import serializers
from .models import Company, Warehouse, Product


class CompanySerializer(serializers.ModelSerializer):
    """Serializer for Company model"""

    warehouses_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "status",
            "created_at",
            "warehouses_count",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "warehouses_count",
        ]

    def get_warehouses_count(self, obj):
        return obj.warehouses.count()


class WarehouseSerializer(serializers.ModelSerializer):
    """Serializer for Warehouse model"""

    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = Warehouse
        fields = [
            "id",
            "company", #company id
            "company_name", #company name
            "name",
            "status",
            "wh_type",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model"""

    unit_of_measure_display = serializers.CharField(
        source="get_unit_of_measure_display", read_only=True
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "sku",
            "name",
            "company",
            "category",
            "unit_of_measure",
            "unit_of_measure_display",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "sku", 'company']
