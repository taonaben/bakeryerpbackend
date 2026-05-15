from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.purchasing.models import (
    PurchaseRequisition,
    PurchaseRequisitionLineItem,
    Supplier,
    SupplierProduct,
)
from apps.purchasing.services.purchase_order_service import create_purchase_order
from central.models import Product, Warehouse


def create_requisition(requested_by, warehouse_id, title, lines, description=""):
    if not lines:
        raise ValidationError("Purchase requisition requires at least one line item.")

    with transaction.atomic():
        warehouse = Warehouse.objects.select_for_update().get(id=warehouse_id)

        requisition = PurchaseRequisition.objects.create(
            requested_by=requested_by,
            warehouse=warehouse,
            title=title,
            description=description or "",
            status="Draft",
        )

        line_items = []
        for line in lines:
            product_id = line.get("product_id")
            if not product_id:
                raise ValidationError("Each line must include a product.")

            product = Product.objects.get(id=product_id)
            quantity = Decimal(str(line.get("quantity", 0)))
            if quantity <= 0:
                raise ValidationError("Line quantity must be greater than zero.")

            unit_of_measure = line.get("unit_of_measure") or product.unit_of_measure

            line_items.append(
                PurchaseRequisitionLineItem(
                    purchase_requisition=requisition,
                    product=product,
                    quantity=quantity,
                    unit_of_measure=unit_of_measure,
                    description=line.get("description", ""),
                )
            )

        PurchaseRequisitionLineItem.objects.bulk_create(line_items)

        return requisition


def submit_requisition(pr_id, submitted_by):
    with transaction.atomic():
        requisition = PurchaseRequisition.objects.select_for_update().get(id=pr_id)

        if requisition.status != "Draft":
            raise ValidationError("Only Draft requisitions can be submitted.")

        if not requisition.line_items.exists():
            raise ValidationError("Requisition must have at least one line item.")

        if requisition.line_items.filter(quantity__lte=0).exists():
            raise ValidationError("Line items must have quantity greater than zero.")

        requisition.status = "Submitted"
        requisition.submitted_by = submitted_by
        requisition.submitted_at = timezone.now()
        requisition.save(
            update_fields=["status", "submitted_by", "submitted_at", "updated_at"]
        )

        return requisition


def create_and_submit_requisition(
    requested_by, submitted_by, warehouse_id, title, lines, description=""
):
    """Create a requisition and immediately submit it in one atomic operation."""
    if not lines:
        raise ValidationError("Purchase requisition requires at least one line item.")

    with transaction.atomic():
        warehouse = Warehouse.objects.select_for_update().get(id=warehouse_id)

        requisition = PurchaseRequisition.objects.create(
            requested_by=requested_by,
            warehouse=warehouse,
            title=title,
            description=description or "",
            status="Submitted",
            submitted_by=submitted_by,
            submitted_at=timezone.now(),
        )

        line_items = []
        for line in lines:
            product_id = line.get("product_id")
            if not product_id:
                raise ValidationError("Each line must include a product.")

            product = Product.objects.get(id=product_id)
            quantity = Decimal(str(line.get("quantity", 0)))
            if quantity <= 0:
                raise ValidationError("Line quantity must be greater than zero.")

            unit_of_measure = line.get("unit_of_measure") or product.unit_of_measure

            line_items.append(
                PurchaseRequisitionLineItem(
                    purchase_requisition=requisition,
                    product=product,
                    quantity=quantity,
                    unit_of_measure=unit_of_measure,
                    description=line.get("description", ""),
                )
            )

        PurchaseRequisitionLineItem.objects.bulk_create(line_items)

        return requisition


def approve_requisition(pr_id, approved_by):
    with transaction.atomic():
        requisition = PurchaseRequisition.objects.select_for_update().get(id=pr_id)

        if requisition.status != "Submitted":
            raise ValidationError("Only Submitted requisitions can be approved.")

        if requisition.requested_by_id == approved_by.id:
            raise ValidationError("Approver must be different from the requester.")

        requisition.status = "Approved"
        requisition.approved_by = approved_by
        requisition.approved_at = timezone.now()
        requisition.save(
            update_fields=["status", "approved_by", "approved_at", "updated_at"]
        )

        return requisition


def reject_requisition(pr_id, rejected_by, reason=""):
    with transaction.atomic():
        requisition = PurchaseRequisition.objects.select_for_update().get(id=pr_id)

        if requisition.status != "Submitted":
            raise ValidationError("Only Submitted requisitions can be rejected.")

        requisition.status = "Rejected"
        requisition.rejected_by = rejected_by
        requisition.rejected_at = timezone.now()
        requisition.rejection_reason = reason or ""
        requisition.save(
            update_fields=[
                "status",
                "rejected_by",
                "rejected_at",
                "rejection_reason",
                "updated_at",
            ]
        )

        return requisition


def convert_to_purchase_order(
    pr_id,
    supplier_id,
    created_by,
    line_overrides=None,
):
    with transaction.atomic():
        requisition = PurchaseRequisition.objects.select_for_update().get(id=pr_id)

        if requisition.status != "Approved":
            raise ValidationError("Only Approved requisitions can be converted.")

        supplier = Supplier.objects.select_for_update().get(id=supplier_id)

        lines = requisition.line_items.select_related("product")
        overrides = {item["pr_line_item_id"]: item for item in line_overrides or []}
        if overrides:
            lines = lines.filter(id__in=list(overrides.keys()))

        if not lines.exists():
            raise ValidationError("No requisition lines selected for conversion.")

        po_lines = []
        for line in lines:
            override = overrides.get(line.id, {})
            override_price = override.get("unit_price")

            supplier_product = SupplierProduct.objects.filter(
                supplier=supplier, product=line.product
            ).first()

            if supplier_product and supplier_product.is_active:
                unit_price = supplier_product.price
            else:
                if override_price is None:
                    raise ValidationError(
                        f"Missing supplier price for {line.product.name}. Provide a unit_price override."
                    )

                unit_price = Decimal(str(override_price))
                if unit_price <= 0:
                    raise ValidationError(
                        "Override unit price must be greater than zero."
                    )

                if supplier_product:
                    supplier_product.price = unit_price
                    supplier_product.is_active = True
                    supplier_product.save(
                        update_fields=["price", "is_active", "updated_at"]
                    )
                else:
                    SupplierProduct.objects.create(
                        supplier=supplier,
                        product=line.product,
                        price=unit_price,
                        lead_time_days=0,
                        is_preferred=False,
                        is_active=True,
                    )

            po_lines.append(
                {
                    "product_id": line.product_id,
                    "supplier_id": str(supplier.id),
                    "quantity": line.quantity,
                    "unit_of_measure": line.unit_of_measure,
                    "unit_price": unit_price,
                    "quoted_price": unit_price,
                    "description": line.description,
                }
            )

        po = create_purchase_order(
            supplier_id=supplier.id,
            warehouse_id=requisition.warehouse_id,
            lines=po_lines,
            created_by=created_by,
            pr_id=requisition.id,
            currency=supplier.currency,
            description=f"Converted from PR {requisition.pr_number}",
        )

        requisition.status = "Converted"
        requisition.converted_at = timezone.now()
        requisition.save(update_fields=["status", "converted_at", "updated_at"])

        return po
