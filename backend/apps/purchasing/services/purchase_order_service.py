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
    SupplierProduct,
)
from central.models import Product, Warehouse


def create_purchase_order(
    warehouse_id,
    lines,
    created_by,
    supplier_id=None,
    pr_id=None,
    currency=None,
    description="",
    expected_delivery_date=None,
):
    """Create a Purchase Order.

    Each line must specify its own ``supplier_id``.  The top-level ``supplier_id``
    is optional and can be used to record a primary/default supplier on the header
    (e.g. when all lines come from the same vendor), but it is no longer required.

    ``quoted_price`` on each line is the supplier's catalogue price (sourced from
    SupplierProduct and pre-filled by the frontend).  ``unit_price`` is the price
    agreed for this specific order and may be adjusted by the user.
    """
    if not lines:
        raise ValidationError("Purchase order requires at least one line item.")

    with transaction.atomic():
        warehouse = Warehouse.objects.select_for_update().get(id=warehouse_id)

        # Validate the optional header-level supplier
        header_supplier = None
        if supplier_id:
            header_supplier = Supplier.objects.select_for_update().get(id=supplier_id)
            if not header_supplier.is_active:
                raise ValidationError(
                    "Header supplier must be active to create a purchase order."
                )
            if header_supplier.on_hold:
                raise ValidationError(
                    f"Supplier '{header_supplier.name}' is on hold and cannot receive new purchase orders. "
                    f"Reason: {header_supplier.on_hold_reason or 'No reason given.'}"
                )

        # Resolve currency: explicit > header supplier > first line supplier
        resolved_currency = currency

        po = PurchaseOrder.objects.create(
            supplier=header_supplier,
            warehouse=warehouse,
            purchase_requisition_id=pr_id,
            created_by=created_by,
            currency=resolved_currency or "",  # filled below once lines are validated
            description=description or "",
            expected_delivery_date=expected_delivery_date,
            status="Draft",
        )

        line_items = []
        first_line_currency = None

        for line in lines:
            product_id = line.get("product_id")
            if not product_id:
                raise ValidationError("Each line must include a product.")

            line_supplier_id = line.get("supplier_id")
            if not line_supplier_id:
                raise ValidationError(
                    "Each line must include a supplier_id for the supplier providing that item."
                )

            product = Product.objects.get(id=product_id)
            line_supplier = Supplier.objects.get(id=line_supplier_id)

            if not line_supplier.is_active:
                raise ValidationError(
                    f"Supplier '{line_supplier.name}' on line for product "
                    f"'{product.name}' is not active."
                )
            if line_supplier.on_hold:
                raise ValidationError(
                    f"Supplier '{line_supplier.name}' is on hold. "
                    f"Reason: {line_supplier.on_hold_reason or 'No reason given.'}"
                )

            quantity = Decimal(str(line.get("quantity", 0)))
            unit_price = Decimal(str(line.get("unit_price", 0)))

            if quantity <= 0 or unit_price <= 0:
                raise ValidationError(
                    "Line quantity and unit price must be greater than zero."
                )

            # quoted_price: use the value passed in (pre-filled from SupplierProduct
            # by the frontend), or look it up automatically as a fallback.
            quoted_price_raw = line.get("quoted_price")
            if quoted_price_raw is not None:
                quoted_price = Decimal(str(quoted_price_raw))
            else:
                sp = SupplierProduct.objects.filter(
                    supplier=line_supplier, product=product, is_active=True
                ).first()
                quoted_price = sp.price if sp else None

            unit_of_measure = line.get("unit_of_measure") or product.unit_of_measure
            total_price = quantity * unit_price

            if first_line_currency is None:
                first_line_currency = line_supplier.currency

            line_items.append(
                PurchaseOrderLineItem(
                    purchase_order=po,
                    supplier=line_supplier,
                    product=product,
                    quantity=quantity,
                    unit_of_measure=unit_of_measure,
                    quoted_price=quoted_price,
                    unit_price=unit_price,
                    total_price=total_price,
                    description=line.get("description", ""),
                )
            )

        PurchaseOrderLineItem.objects.bulk_create(line_items)

        # Resolve currency now that we have line data
        if not po.currency:
            po.currency = (
                (header_supplier.currency if header_supplier else None)
                or first_line_currency
                or ""
            )
            po.save(update_fields=["currency", "updated_at"])

        recalculate_total(po.id)

        return po


def submit_po(po_id, submitted_by):
    with transaction.atomic():
        po = PurchaseOrder.objects.select_for_update().get(id=po_id)

        if po.status != "Draft":
            raise ValidationError("Only Draft purchase orders can be submitted.")

        if not po.line_items.exists():
            raise ValidationError("Purchase order must have at least one line item.")

        # Validate that every line has an active, non-held supplier
        for line in po.line_items.select_related("supplier"):
            if not line.supplier:
                raise ValidationError(
                    f"Line for product '{line.product_id}' is missing a supplier."
                )
            if not line.supplier.is_active:
                raise ValidationError(
                    f"Supplier '{line.supplier.name}' on a line item is not active."
                )
            if line.supplier.on_hold:
                raise ValidationError(
                    f"Supplier '{line.supplier.name}' is on hold."
                )

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
