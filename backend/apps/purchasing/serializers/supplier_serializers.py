from rest_framework import serializers

from central.models import Warehouse
from apps.purchasing.models import (
    Supplier,
    SupplierContact,
    SupplierDocument,
    SupplierProduct,
)


class SupplierContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierContact
        fields = [
            "id",
            "supplier",
            "name",
            "role",
            "email",
            "phone",
            "is_primary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SupplierContactCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierContact
        fields = ["supplier", "name", "role", "email", "phone", "is_primary"]


class SupplierDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierDocument
        fields = [
            "id",
            "supplier",
            "document_type",
            "name",
            "file_url",
            "file_name",
            "issued_date",
            "expiry_date",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SupplierDocumentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierDocument
        fields = [
            "supplier",
            "document_type",
            "name",
            "file_url",
            "file_name",
            "issued_date",
            "expiry_date",
            "notes",
            "is_active",
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


class SupplierSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    contacts = SupplierContactSerializer(many=True, read_only=True)
    documents = SupplierDocumentSerializer(many=True, read_only=True)
    warehouses_served = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    products = SupplierProductSerializer(
        source="supplier_products", many=True, read_only=True
    )

    class Meta:
        model = Supplier
        fields = [
            "id",
            "company",
            "company_name",
            # Identity & Compliance
            "name",
            "registration_number",
            "tax_number",
            "supplier_type",
            # Contact & Location
            "primary_email",
            "secondary_email",
            "primary_phone",
            "alternate_phone",
            "address",
            "country",
            "city",
            "website",
            # Financial
            "payment_terms",
            "currency",
            "credit_limit",
            "bank_name",
            "bank_branch",
            "bank_account_number",
            "can_supply_on_credit",
            # Logistics
            "default_lead_time_days",
            "minimum_order_value",
            "delivery_days",
            "delivery_method",
            "delivery_radius_km",
            "warehouses_served",
            # Performance & Internal
            "rating",
            "internal_notes",
            "on_hold",
            "on_hold_reason",
            "is_active",
            "created_at",
            "updated_at",
            # Related
            "contacts",
            "documents",
            "products",
        ]
        read_only_fields = ["id", "is_active", "created_at", "updated_at"]


class SupplierCreateUpdateSerializer(serializers.ModelSerializer):
    warehouses_served = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Warehouse.objects.all(),
        required=False,
    )

    class Meta:
        model = Supplier
        fields = [
            "company",
            # Identity & Compliance
            "name",
            "registration_number",
            "tax_number",
            "supplier_type",
            # Contact & Location
            "primary_email",
            "secondary_email",
            "primary_phone",
            "alternate_phone",
            "address",
            "country",
            "city",
            "website",
            # Financial
            "payment_terms",
            "currency",
            "credit_limit",
            "bank_name",
            "bank_branch",
            "bank_account_number",
            "can_supply_on_credit",
            # Logistics
            "default_lead_time_days",
            "minimum_order_value",
            "delivery_days",
            "delivery_method",
            "delivery_radius_km",
            "warehouses_served",
            # Performance & Internal
            "rating",
            "internal_notes",
            "on_hold",
            "on_hold_reason",
        ]


class SupplierPutOnHoldSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
