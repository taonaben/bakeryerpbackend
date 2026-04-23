import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.accounting.models import ACCOUNT_AP, ACCOUNT_BANK, ACCOUNT_INVENTORY
from apps.accounting.services import post_journal_entry
from apps.purchasing.models import (
    PurchaseOrder,
    PurchasingConfig,
    SupplierInvoice,
    SupplierInvoiceLineItem,
)

logger = logging.getLogger(__name__)


def create_invoice(po_id, supplier_id, invoice_date, due_date, lines, created_by=None):
    if not lines:
        raise ValidationError("Invoice requires at least one line item.")

    with transaction.atomic():
        # Lock only the PurchaseOrder row, fetch related objects separately to avoid FOR UPDATE on nullable side
        po = PurchaseOrder.objects.select_for_update().get(id=po_id)
        # Fetch related objects (supplier, warehouse) after locking
        po_supplier = po.supplier  # May trigger a DB query if not cached
        po_warehouse = po.warehouse

        if po.status not in ("Partially Received", "Received"):
            raise ValidationError(
                "Purchase order must be Partially Received or Received."
            )

        if str(po.supplier_id) != str(supplier_id):
            raise ValidationError(
                "Supplier does not match the purchase order supplier."
            )

        invoice = SupplierInvoice.objects.create(
            purchase_order=po,
            supplier=po_supplier,
            warehouse=po_warehouse,
            invoice_date=invoice_date,
            due_date=due_date,
            status="Draft",
        )

        invoice_lines = []
        for line in lines:
            gr_line_item_id = line.get("gr_line_item_id")
            product_id = line.get("product_id")
            quantity_invoiced = Decimal(str(line.get("quantity_invoiced", 0)))
            unit_price = Decimal(str(line.get("unit_price", 0)))

            if quantity_invoiced <= 0:
                raise ValidationError("Invoiced quantity must be greater than zero.")
            if unit_price <= 0:
                raise ValidationError("Unit price must be greater than zero.")

            # Over-invoice guard: check total invoiced across all invoices for this PO + product
            if gr_line_item_id:
                from apps.purchasing.models import GoodsReceiptLineItem

                gr_line = GoodsReceiptLineItem.objects.select_related(
                    "goods_receipt", "po_line_item"
                ).get(id=gr_line_item_id)

                if gr_line.goods_receipt.purchase_order_id != po.id:
                    raise ValidationError(
                        "GRN line does not belong to this purchase order."
                    )

                if gr_line.goods_receipt.status != "Approved":
                    raise ValidationError("GRN must be Approved to invoice against it.")

                # Sum already-invoiced qty for this GRN line across non-rejected invoices
                already_invoiced = SupplierInvoiceLineItem.objects.filter(
                    gr_line_item_id=gr_line_item_id,
                    supplier_invoice__purchase_order=po,
                ).exclude(supplier_invoice__status="Rejected").aggregate(
                    total=Sum("quantity_invoiced")
                )[
                    "total"
                ] or Decimal(
                    "0"
                )

                if already_invoiced + quantity_invoiced > gr_line.quantity_received:
                    raise ValidationError(
                        f"Invoiced quantity exceeds received quantity for GRN line {gr_line_item_id}."
                    )

            # Set total_price manually since bulk_create does not call save()
            total_price = quantity_invoiced * unit_price
            invoice_lines.append(
                SupplierInvoiceLineItem(
                    supplier_invoice=invoice,
                    gr_line_item_id=gr_line_item_id,
                    product_id=product_id,
                    quantity_invoiced=quantity_invoiced,
                    unit_of_measure=line.get("unit_of_measure", ""),
                    unit_price=unit_price,
                    total_price=total_price,
                    description=line.get("description", ""),
                )
            )

        SupplierInvoiceLineItem.objects.bulk_create(invoice_lines)

        # Recalculate total from saved lines
        total = SupplierInvoiceLineItem.objects.filter(
            supplier_invoice=invoice
        ).aggregate(total=Sum("total_price"))["total"] or Decimal("0")
        invoice.total_amount = total
        invoice.save(update_fields=["total_amount", "updated_at"])

        return invoice


def match_invoice(invoice_id):
    invoice = SupplierInvoice.objects.select_related(
        "purchase_order__warehouse__company"
    ).get(id=invoice_id)

    company = invoice.purchase_order.warehouse.company

    # Load tolerance config
    try:
        config = PurchasingConfig.objects.get(company=company)
        price_tol = config.price_tolerance_pct / Decimal("100")
        qty_tol = config.qty_tolerance_pct / Decimal("100")
    except PurchasingConfig.DoesNotExist:
        price_tol = Decimal("0")
        qty_tol = Decimal("0")

    inv_lines = SupplierInvoiceLineItem.objects.select_related(
        "gr_line_item__po_line_item", "product"
    ).filter(supplier_invoice=invoice)

    result = {
        "matched": [],
        "price_variance": [],
        "qty_variance": [],
        "unmatched": [],
    }

    for inv_line in inv_lines:
        line_data = {
            "invoice_line_id": str(inv_line.id),
            "product_id": str(inv_line.product_id),
            "product_name": inv_line.product.name if inv_line.product else "",
            "invoice_qty": inv_line.quantity_invoiced,
            "invoice_unit_price": inv_line.unit_price,
        }

        gr_line = inv_line.gr_line_item
        if not gr_line:
            line_data["reason"] = "No GRN line linked"
            result["unmatched"].append(line_data)
            continue

        po_line = gr_line.po_line_item
        if not po_line:
            line_data["reason"] = "GRN line has no PO line reference"
            result["unmatched"].append(line_data)
            continue

        line_data.update(
            {
                "gr_qty": gr_line.quantity_received,
                "gr_unit_price": gr_line.unit_price,
                "po_qty": po_line.quantity,
                "po_unit_price": po_line.unit_price,
            }
        )

        # Check price: compare all three
        def _within_tolerance(a, b, tolerance):
            if b == 0:
                return a == 0
            return abs(a - b) / b <= tolerance

        price_ok = _within_tolerance(
            inv_line.unit_price, po_line.unit_price, price_tol
        ) and _within_tolerance(inv_line.unit_price, gr_line.unit_price, price_tol)

        qty_ok = _within_tolerance(
            inv_line.quantity_invoiced, gr_line.quantity_received, qty_tol
        )

        if price_ok and qty_ok:
            result["matched"].append(line_data)
        elif not price_ok and qty_ok:
            line_data["price_diff_po"] = float(inv_line.unit_price - po_line.unit_price)
            line_data["price_diff_gr"] = float(inv_line.unit_price - gr_line.unit_price)
            result["price_variance"].append(line_data)
        elif price_ok and not qty_ok:
            line_data["qty_diff_gr"] = float(
                inv_line.quantity_invoiced - gr_line.quantity_received
            )
            result["qty_variance"].append(line_data)
        else:
            line_data["price_diff_po"] = float(inv_line.unit_price - po_line.unit_price)
            line_data["qty_diff_gr"] = float(
                inv_line.quantity_invoiced - gr_line.quantity_received
            )
            result["price_variance"].append(line_data)

    return result


def approve_invoice(invoice_id, approved_by):
    with transaction.atomic():
        # Lock only the invoice row. Fetch nullable related objects separately to
        # avoid PostgreSQL FOR UPDATE errors on outer joins.
        invoice = SupplierInvoice.objects.select_for_update().get(id=invoice_id)
        purchase_order = invoice.purchase_order
        warehouse = purchase_order.warehouse if purchase_order else None
        company = warehouse.company if warehouse else None

        if invoice.status != "Draft":
            raise ValidationError("Only Draft invoices can be approved.")

        if not purchase_order or not warehouse or not company:
            raise ValidationError(
                "Supplier invoice must be linked to a purchase order warehouse and company."
            )

        # Run 3-way match — warn but don't block
        match_result = match_invoice(invoice_id)
        has_variances = bool(
            match_result["price_variance"]
            or match_result["qty_variance"]
            or match_result["unmatched"]
        )
        if has_variances:
            logger.warning(
                "Invoice %s approved with variances: price=%d, qty=%d, unmatched=%d",
                invoice.invoice_number,
                len(match_result["price_variance"]),
                len(match_result["qty_variance"]),
                len(match_result["unmatched"]),
            )

        invoice.status = "Approved"
        invoice.approved_by = approved_by
        invoice.save(update_fields=["status", "approved_by", "updated_at"])

        # Post journal entry: Dr Accounts Payable / Cr Inventory
        post_journal_entry(
            company=company,
            entry_date=invoice.invoice_date,
            reference=invoice.invoice_number,
            description=f"Supplier invoice {invoice.invoice_number} approved",
            source_type="supplier_invoice",
            source_id=invoice.id,
            lines=[
                {
                    "account_code": ACCOUNT_AP,
                    "debit": invoice.total_amount,
                    "credit": Decimal("0"),
                    "description": "Accounts Payable",
                },
                {
                    "account_code": ACCOUNT_INVENTORY,
                    "debit": Decimal("0"),
                    "credit": invoice.total_amount,
                    "description": "Inventory",
                },
            ],
            created_by=approved_by,
        )

        return invoice, match_result


def reject_invoice(invoice_id, rejected_by, reason=""):
    with transaction.atomic():
        invoice = SupplierInvoice.objects.select_for_update().get(id=invoice_id)

        if invoice.status != "Draft":
            raise ValidationError("Only Draft invoices can be rejected.")

        invoice.status = "Rejected"
        invoice.rejected_by = rejected_by
        invoice.rejection_reason = reason or ""
        invoice.save(
            update_fields=[
                "status",
                "rejected_by",
                "rejection_reason",
                "updated_at",
            ]
        )

        return invoice


def mark_paid(invoice_id, paid_by, payment_reference=""):
    with transaction.atomic():
        # Lock only the invoice row. Fetch nullable related objects separately to
        # avoid PostgreSQL FOR UPDATE errors on outer joins.
        invoice = SupplierInvoice.objects.select_for_update().get(id=invoice_id)
        purchase_order = invoice.purchase_order
        warehouse = purchase_order.warehouse if purchase_order else None
        company = warehouse.company if warehouse else None

        if invoice.status != "Approved":
            raise ValidationError("Only Approved invoices can be marked as paid.")

        if not purchase_order or not warehouse or not company:
            raise ValidationError(
                "Supplier invoice must be linked to a purchase order warehouse and company."
            )

        invoice.status = "Paid"
        invoice.paid_by = paid_by
        invoice.payment_reference = payment_reference or ""
        invoice.save(
            update_fields=[
                "status",
                "paid_by",
                "payment_reference",
                "updated_at",
            ]
        )

        # Post journal entry: Dr Accounts Payable / Cr Bank
        post_journal_entry(
            company=company,
            entry_date=invoice.invoice_date,
            reference=invoice.invoice_number,
            description=f"Payment for invoice {invoice.invoice_number}",
            source_type="supplier_invoice_payment",
            source_id=invoice.id,
            lines=[
                {
                    "account_code": ACCOUNT_AP,
                    "debit": invoice.total_amount,
                    "credit": Decimal("0"),
                    "description": "Accounts Payable",
                },
                {
                    "account_code": ACCOUNT_BANK,
                    "debit": Decimal("0"),
                    "credit": invoice.total_amount,
                    "description": "Bank",
                },
            ],
            created_by=paid_by,
        )

        return invoice
