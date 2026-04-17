from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.purchasing.models import (
    GoodsReceipt,
    PurchaseOrder,
    PurchaseOrderLineItem,
    Supplier,
)
from central.models import Product, Warehouse


def create_purchase_order(
    supplier_id,
    warehouse_id,
    lines,
    created_by,
    pr_id=None,
    currency=None,
    description="",
    expected_delivery_date=None,
):
    if not lines:
        raise ValidationError("Purchase order requires at least one line item.")

    with transaction.atomic():
        supplier = Supplier.objects.select_for_update().get(id=supplier_id)
        if not supplier.is_active:
            raise ValidationError("Supplier must be active to create a purchase order.")
        if supplier.on_hold:
            raise ValidationError(
                f"Supplier '{supplier.name}' is on hold and cannot receive new purchase orders. "
                f"Reason: {supplier.on_hold_reason or 'No reason given.'}"
            )

        warehouse = Warehouse.objects.select_for_update().get(id=warehouse_id)

        po = PurchaseOrder.objects.create(
            supplier=supplier,
            warehouse=warehouse,
            purchase_requisition_id=pr_id,
            created_by=created_by,
            currency=currency or supplier.currency,
            description=description or "",
            expected_delivery_date=expected_delivery_date,
            status="Draft",
        )

        line_items = []
        for line in lines:
            product_id = line.get("product_id")
            if not product_id:
                raise ValidationError("Each line must include a product.")

            product = Product.objects.get(id=product_id)

            quantity = Decimal(str(line.get("quantity", 0)))
            unit_price = Decimal(str(line.get("unit_price", 0)))

            if quantity <= 0 or unit_price <= 0:
                raise ValidationError(
                    "Line quantity and unit price must be greater than zero."
                )

            unit_of_measure = line.get("unit_of_measure") or product.unit_of_measure

            line_items.append(
                PurchaseOrderLineItem(
                    purchase_order=po,
                    product=product,
                    quantity=quantity,
                    unit_of_measure=unit_of_measure,
                    unit_price=unit_price,
                    description=line.get("description", ""),
                )
            )

        PurchaseOrderLineItem.objects.bulk_create(line_items)
        recalculate_total(po.id)

        return po


def submit_po(po_id, submitted_by):
    with transaction.atomic():
        po = PurchaseOrder.objects.select_for_update().get(id=po_id)

        if po.status != "Draft":
            raise ValidationError("Only Draft purchase orders can be submitted.")

        if not po.supplier.is_active:
            raise ValidationError("Supplier must be active to submit a purchase order.")

        if not po.line_items.exists():
            raise ValidationError("Purchase order must have at least one line item.")

        invalid_line_exists = (
            po.line_items.filter(quantity__lte=0).exists()
            or po.line_items.filter(unit_price__lte=0).exists()
        )
        if invalid_line_exists:
            raise ValidationError(
                "Line items must have quantity and unit price greater than zero."
            )

        recalculate_total(po.id)

        if po.total_amount <= 0:
            raise ValidationError("Purchase order total must be greater than zero.")

        po.status = "Submitted"
        po.submitted_by = submitted_by
        po.submitted_at = timezone.now()
        po.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])

        return po


def approve_po(po_id, approved_by):
    with transaction.atomic():
        po = PurchaseOrder.objects.select_for_update().get(id=po_id)

        if po.status != "Submitted":
            raise ValidationError("Only Submitted purchase orders can be approved.")

        if po.created_by and po.created_by_id == approved_by.id:
            raise ValidationError("Approver must be different from the creator.")

        po.status = "Approved"
        po.approved_by = approved_by
        po.approved_at = timezone.now()
        po.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

        return po


def reject_po(po_id, rejected_by, reason=""):
    with transaction.atomic():
        po = PurchaseOrder.objects.select_for_update().get(id=po_id)

        if po.status != "Submitted":
            raise ValidationError("Only Submitted purchase orders can be rejected.")

        po.status = "Rejected"
        po.rejected_by = rejected_by
        po.rejected_at = timezone.now()
        po.rejection_reason = reason or ""
        po.save(
            update_fields=[
                "status",
                "rejected_by",
                "rejected_at",
                "rejection_reason",
                "updated_at",
            ]
        )

        return po


def cancel_po(po_id, cancelled_by):
    with transaction.atomic():
        po = PurchaseOrder.objects.select_for_update().get(id=po_id)

        if po.status not in ["Draft", "Approved"]:
            raise ValidationError(
                "Only Draft or Approved purchase orders can be cancelled."
            )

        if GoodsReceipt.objects.filter(purchase_order=po).exists():
            raise ValidationError(
                "Cannot cancel a purchase order with any goods receipts."
            )

        po.status = "Cancelled"
        po.cancelled_by = cancelled_by
        po.cancelled_at = timezone.now()
        po.save(update_fields=["status", "cancelled_by", "cancelled_at", "updated_at"])

        return po


def recalculate_total(po_id):
    po = PurchaseOrder.objects.get(id=po_id)
    totals = po.line_items.aggregate(total_amount=Sum("total_price"))
    po.total_amount = totals["total_amount"] or 0
    po.save(update_fields=["total_amount", "updated_at"])
    return po


def update_status_from_grn(po_id):
    po = PurchaseOrder.objects.select_related("warehouse").get(id=po_id)

    if po.status in ["Rejected", "Cancelled"]:
        return po

    line_items = po.line_items.all()
    if not line_items.exists():
        return po

    any_received = line_items.filter(quantity_received__gt=0).exists()
    all_received = not line_items.filter(quantity_received__lt=F("quantity")).exists()

    if all_received and po.status != "Received":
        po.status = "Received"
        po.save(update_fields=["status", "updated_at"])
        return po

    if any_received and po.status != "Partially Received":
        po.status = "Partially Received"
        po.save(update_fields=["status", "updated_at"])

    return po
