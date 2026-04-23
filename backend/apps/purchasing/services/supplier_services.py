from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.purchasing.models import (
    PurchaseOrder,
    Supplier,
    SupplierContact,
    SupplierDocument,
    SupplierProduct,
)

OPEN_PO_STATUSES = ("Draft", "Approved", "Submitted", "Partially Received")

SUPPLIER_UPDATABLE_FIELDS = (
    "name",
    "registration_number",
    "tax_number",
    "supplier_type",
    "primary_email",
    "secondary_email",
    "primary_phone",
    "alternate_phone",
    "address",
    "country",
    "city",
    "website",
    "payment_terms",
    "currency",
    "credit_limit",
    "bank_name",
    "bank_branch",
    "bank_account_number",
    "can_supply_on_credit",
    "default_lead_time_days",
    "minimum_order_value",
    "delivery_days",
    "delivery_method",
    "delivery_radius_km",
    "rating",
    "internal_notes",
)


def create_supplier(data):
    return Supplier.objects.create(**data)


def update_supplier(supplier_id, data):
    with transaction.atomic():
        supplier = Supplier.objects.select_for_update().get(id=supplier_id)

        scalar_fields = [f for f in SUPPLIER_UPDATABLE_FIELDS if f in data]
        for field in scalar_fields:
            setattr(supplier, field, data[field])

        if scalar_fields:
            supplier.save(update_fields=scalar_fields + ["updated_at"])

        if "warehouses_served" in data:
            supplier.warehouses_served.set(data["warehouses_served"])

        return supplier


def deactivate_supplier(supplier_id):
    with transaction.atomic():
        supplier = Supplier.objects.select_for_update().get(id=supplier_id)

        if not supplier.is_active:
            raise ValidationError("Supplier is already inactive.")

        open_pos = PurchaseOrder.objects.filter(
            supplier=supplier,
            status__in=OPEN_PO_STATUSES,
        ).count()

        if open_pos:
            raise ValidationError(
                f"Cannot deactivate supplier with {open_pos} open purchase order(s)."
            )

        supplier.is_active = False
        supplier.save(update_fields=["is_active", "updated_at"])
        return supplier


def reactivate_supplier(supplier_id):
    with transaction.atomic():
        supplier = Supplier.objects.select_for_update().get(id=supplier_id)

        if supplier.is_active:
            raise ValidationError("Supplier is already active.")

        supplier.is_active = True
        supplier.save(update_fields=["is_active", "updated_at"])
        return supplier


def add_product_to_catalogue(
    supplier_id, product_id, price, lead_time_days, is_preferred=False
):
    with transaction.atomic():
        supplier = Supplier.objects.select_for_update().get(id=supplier_id)

        if not supplier.is_active:
            raise ValidationError("Cannot add products to an inactive supplier.")

        if is_preferred:
            SupplierProduct.objects.filter(
                product_id=product_id,
                is_preferred=True,
                supplier__company=supplier.company,
            ).update(is_preferred=False)

        try:
            sp = SupplierProduct.objects.create(
                supplier=supplier,
                product_id=product_id,
                price=price,
                lead_time_days=lead_time_days,
                is_preferred=is_preferred,
            )
        except IntegrityError:
            raise ValidationError(
                "This product is already in the supplier's catalogue."
            )

        return sp


def get_preferred_supplier(product_id, company_id=None):
    qs = SupplierProduct.objects.select_related("supplier", "product").filter(
        product_id=product_id,
        is_preferred=True,
        is_active=True,
        supplier__is_active=True,
    )
    if company_id:
        qs = qs.filter(supplier__company_id=company_id)
    return qs.first()


def put_supplier_on_hold(supplier_id, reason):
    with transaction.atomic():
        supplier = Supplier.objects.select_for_update().get(id=supplier_id)
        if supplier.on_hold:
            raise ValidationError("Supplier is already on hold.")
        supplier.on_hold = True
        supplier.on_hold_reason = reason or ""
        supplier.save(update_fields=["on_hold", "on_hold_reason", "updated_at"])
        return supplier


def release_supplier_hold(supplier_id):
    with transaction.atomic():
        supplier = Supplier.objects.select_for_update().get(id=supplier_id)
        if not supplier.on_hold:
            raise ValidationError("Supplier is not currently on hold.")
        supplier.on_hold = False
        supplier.on_hold_reason = ""
        supplier.save(update_fields=["on_hold", "on_hold_reason", "updated_at"])
        return supplier


def create_supplier_contact(supplier_id, data):
    with transaction.atomic():
        supplier = Supplier.objects.get(id=supplier_id)
        is_primary = data.get("is_primary", False)
        if is_primary:
            # Soft-enforce: clear existing primary before setting new one
            SupplierContact.objects.filter(supplier=supplier, is_primary=True).update(
                is_primary=False
            )
        contact = SupplierContact.objects.create(supplier=supplier, **data)
        return contact


def create_supplier_document(supplier_id, data):
    supplier = Supplier.objects.get(id=supplier_id)
    return SupplierDocument.objects.create(supplier=supplier, **data)
