from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from apps.inventory.models import Batch, StockMovement, StockMovementBatch
from apps.purchasing.models import (
    GoodsReceipt,
    GoodsReceiptLineItem,
    PurchaseOrder,
    PurchaseOrderLineItem,
)
from apps.purchasing.services.purchase_order_service import update_status_from_grn


class GoodsReceiptService:
    @staticmethod
    def create_grn(po_id, warehouse_id, received_by, lines):
        if not lines:
            raise ValidationError("Goods receipt requires at least one line item.")

        with transaction.atomic():
            po = (
                PurchaseOrder.objects.select_for_update()
                .select_related("warehouse")
                .get(id=po_id)
            )

            if po.status not in ["Approved", "Partially Received"]:
                raise ValidationError(
                    "Purchase order must be Approved or Partially Received."
                )

            if not po.warehouse or str(po.warehouse.id) != str(warehouse_id):
                raise ValidationError(
                    "Warehouse must match the purchase order warehouse."
                )

            grn = GoodsReceipt.objects.create(
                purchase_order=po,
                warehouse=po.warehouse,
                received_by=received_by,
                status="Draft",
            )

            line_items = []
            running_received = {}
            for line in lines:
                po_line_id = line.get("po_line_item_id")
                if not po_line_id:
                    raise ValidationError(
                        "Each line must reference a purchase order line item."
                    )

                po_line = PurchaseOrderLineItem.objects.select_for_update().get(
                    id=po_line_id
                )

                if po_line.purchase_order_id != po.id:
                    raise ValidationError(
                        "Line item does not belong to the purchase order."
                    )

                line_qty = Decimal(str(line.get("quantity_received", 0)))
                if line_qty <= 0:
                    raise ValidationError(
                        "Received quantity must be greater than zero."
                    )

                current_received = running_received.get(
                    po_line_id, po_line.quantity_received
                )
                remaining_qty = po_line.quantity - current_received
                if line_qty > remaining_qty:
                    raise ValidationError(
                        "Received quantity exceeds remaining PO quantity."
                    )

                running_received[po_line_id] = current_received + line_qty

                line_items.append(
                    GoodsReceiptLineItem(
                        goods_receipt=grn,
                        po_line_item=po_line,
                        product=po_line.product,
                        quantity_received=line_qty,
                        unit_of_measure=line.get("unit_of_measure")
                        or po_line.unit_of_measure,
                        supplier_batch_ref=line.get("supplier_batch_ref", ""),
                        expiry_date=line.get("expiry_date"),
                        manufacturing_date=line.get("manufacturing_date"),
                        description=line.get("description", ""),
                    )
                )

            GoodsReceiptLineItem.objects.bulk_create(line_items)

            return grn

    @staticmethod
    def confirm_grn(grn_id, confirmed_by=None):
        with transaction.atomic():
            grn = (
                GoodsReceipt.objects.select_for_update()
                .select_related("purchase_order", "warehouse")
                .get(id=grn_id)
            )

            if grn.status != "Draft":
                raise ValidationError(
                    "Goods receipt must be in Draft status to confirm."
                )

            po = grn.purchase_order
            if po.status not in ["Approved", "Partially Received"]:
                raise ValidationError(
                    "Purchase order must be Approved or Partially Received."
                )

            if (
                not grn.warehouse
                or not po.warehouse
                or grn.warehouse_id != po.warehouse_id
            ):
                raise ValidationError(
                    "Goods receipt warehouse must match purchase order warehouse."
                )

            line_items = (
                GoodsReceiptLineItem.objects.select_for_update()
                .select_related("po_line_item", "product")
                .filter(goods_receipt=grn)
            )

            if not line_items.exists():
                raise ValidationError("Goods receipt must have at least one line item.")

            locked_po_lines = {}
            running_received = {}

            for line in line_items:
                if not line.po_line_item:
                    raise ValidationError(
                        "Goods receipt line item is missing a PO line item."
                    )

                po_line_id = line.po_line_item_id
                if po_line_id not in locked_po_lines:
                    locked_po_lines[
                        po_line_id
                    ] = PurchaseOrderLineItem.objects.select_for_update().get(
                        id=po_line_id
                    )

                po_line = locked_po_lines[po_line_id]

                if po_line.purchase_order_id != po.id:
                    raise ValidationError(
                        "Goods receipt line item does not belong to the PO."
                    )

                current_received = running_received.get(
                    po_line_id, po_line.quantity_received
                )
                remaining_qty = po_line.quantity - current_received
                if line.quantity_received > remaining_qty:
                    raise ValidationError(
                        "Received quantity exceeds remaining PO quantity."
                    )

                running_received[po_line_id] = current_received + line.quantity_received

                batch = GoodsReceiptService._resolve_batch(grn, line)

                movement = StockMovement.objects.create(
                    warehouse=grn.warehouse,
                    movement_type="IN",
                    total_quantity=line.quantity_received,
                    reference_number=grn.gr_number,
                    notes=None,
                )

                StockMovementBatch.objects.create(
                    stock_movement=movement,
                    batch=batch,
                    quantity=line.quantity_received,
                )

                PurchaseOrderLineItem.objects.filter(id=po_line.id).update(
                    quantity_received=F("quantity_received") + line.quantity_received
                )

            if confirmed_by:
                grn.received_by = confirmed_by

            grn.status = "Approved"
            grn.save(update_fields=["status", "received_by", "updated_at"])

            update_status_from_grn(po.id)

            return grn

    @staticmethod
    def reject_grn(grn_id, rejected_by=None, reason=""):
        with transaction.atomic():
            grn = GoodsReceipt.objects.select_for_update().get(id=grn_id)

            if grn.status != "Draft":
                raise ValidationError(
                    "Goods receipt must be in Draft status to reject."
                )

            if rejected_by:
                grn.received_by = rejected_by

            grn.status = "Rejected"
            grn.rejection_reason = reason or ""
            grn.save(
                update_fields=[
                    "status",
                    "rejection_reason",
                    "received_by",
                    "updated_at",
                ]
            )

            return grn

    @staticmethod
    def _resolve_batch(grn, line):
        supplier_ref = (line.supplier_batch_ref or "").strip()
        if supplier_ref:
            batch = Batch.objects.filter(
                product=line.product,
                warehouse=grn.warehouse,
                batch_number=supplier_ref,
                warehouse__company=grn.warehouse.company,
            ).first()

            if batch:
                return batch

            return Batch.objects.create(
                product=line.product,
                warehouse=grn.warehouse,
                batch_number=supplier_ref,
                quantity=0,
                manufacture_date=line.manufacturing_date,
                expiry_date=line.expiry_date,
            )

        return Batch.objects.create(
            product=line.product,
            warehouse=grn.warehouse,
            batch_number=Batch.generate_batch_number(),
            quantity=0,
            manufacture_date=line.manufacturing_date,
            expiry_date=line.expiry_date,
        )
