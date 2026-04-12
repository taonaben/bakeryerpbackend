from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.purchasing.models import PurchaseOrder, Supplier, SupplierProduct

OPEN_PO_STATUSES = ("Draft", "Approved", "Submitted", "Partially Received")

SUPPLIER_UPDATABLE_FIELDS = (
    "name",
    "contact_person",
    "email",
    "phone_number",
    "address",
    "payment_terms",
    "currency",
)


def create_supplier(data):
    return Supplier.objects.create(**data)


def update_supplier(supplier_id, data):
    with transaction.atomic():
        supplier = Supplier.objects.select_for_update().get(id=supplier_id)

        for field in SUPPLIER_UPDATABLE_FIELDS:
            if field in data:
                setattr(supplier, field, data[field])

        supplier.save(
            update_fields=[f for f in SUPPLIER_UPDATABLE_FIELDS if f in data]
            + ["updated_at"]
        )
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
