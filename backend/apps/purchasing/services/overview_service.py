from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from django.utils import timezone

from apps.purchasing.models import (
    GoodsReceipt,
    GoodsReceiptLineItem,
    PurchaseOrder,
    PurchaseRequisition,
    PurchasingConfig,
    Supplier,
    SupplierDocument,
    SupplierInvoice,
    SupplierInvoiceLineItem,
)


PR_STATUSES = ["Draft", "Submitted", "Approved", "Rejected", "Converted"]
PO_STATUSES = [
    "Draft",
    "Submitted",
    "Approved",
    "Partially Received",
    "Received",
    "Rejected",
    "Cancelled",
]
GRN_STATUSES = ["Draft", "Approved", "Rejected"]
SUPPLIER_INVOICE_STATUSES = ["Draft", "Approved", "Rejected", "Paid"]
OPEN_PO_VALUE_STATUSES = ["Submitted", "Approved", "Partially Received"]
OVERDUE_PO_STATUSES = ["Submitted", "Approved"]
NON_EXCEPTION_INVOICE_STATUSES = ["Draft", "Approved", "Paid"]


class PurchasingOverviewService:
    @staticmethod
    def summary(company, *, warehouse_id=None, expiring_within_days=30):
        today = timezone.localdate()

        requisitions = PurchaseRequisition.objects.filter(warehouse__company=company)
        purchase_orders = PurchaseOrder.objects.filter(warehouse__company=company)
        goods_receipts = GoodsReceipt.objects.filter(warehouse__company=company)
        invoices = SupplierInvoice.objects.filter(warehouse__company=company)
        suppliers = Supplier.objects.filter(company=company)
        documents = SupplierDocument.objects.filter(supplier__company=company)

        if warehouse_id:
            requisitions = requisitions.filter(warehouse_id=warehouse_id)
            purchase_orders = purchase_orders.filter(warehouse_id=warehouse_id)
            goods_receipts = goods_receipts.filter(warehouse_id=warehouse_id)
            invoices = invoices.filter(warehouse_id=warehouse_id)

        overdue_pos = purchase_orders.filter(
            status__in=OVERDUE_PO_STATUSES,
            expected_delivery_date__lt=today,
        )
        open_po_value = purchase_orders.filter(
            status__in=OPEN_PO_VALUE_STATUSES
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

        expiring_cutoff = today + timedelta(days=expiring_within_days)
        exception_summary = PurchasingOverviewService.match_exception_summary(
            company,
            warehouse_id=warehouse_id,
        )

        return {
            "as_of_date": today,
            "warehouse_id": warehouse_id,
            "pr_counts_by_status": PurchasingOverviewService._count_by_status(
                requisitions, PR_STATUSES
            ),
            "po_counts_by_status": PurchasingOverviewService._count_by_status(
                purchase_orders, PO_STATUSES
            ),
            "open_po_value": open_po_value,
            "overdue_pos": {
                "count": overdue_pos.count(),
                "value": overdue_pos.aggregate(total=Sum("total_amount"))["total"]
                or Decimal("0"),
            },
            "grn_counts_by_status": PurchasingOverviewService._count_by_status(
                goods_receipts, GRN_STATUSES
            ),
            "supplier_invoice_counts_by_status": PurchasingOverviewService._count_by_status(
                invoices, SUPPLIER_INVOICE_STATUSES
            ),
            "pending_approvals": {
                "submitted_prs": requisitions.filter(status="Submitted").count(),
                "submitted_pos": purchase_orders.filter(status="Submitted").count(),
                "draft_grns": goods_receipts.filter(status="Draft").count(),
                "draft_supplier_invoices": invoices.filter(status="Draft").count(),
            },
            "supplier_risk": {
                "suppliers_on_hold": suppliers.filter(on_hold=True).count(),
                "inactive_suppliers": suppliers.filter(is_active=False).count(),
                "expired_documents": documents.filter(
                    is_active=True,
                    expiry_date__lt=today,
                ).count(),
                "expiring_documents": documents.filter(
                    is_active=True,
                    expiry_date__gte=today,
                    expiry_date__lte=expiring_cutoff,
                ).count(),
                "expiring_within_days": expiring_within_days,
            },
            "match_exceptions": exception_summary,
        }

    @staticmethod
    def trends(
        company,
        *,
        date_from=None,
        date_to=None,
        warehouse_id=None,
        interval="month",
    ):
        purchase_orders = PurchaseOrder.objects.filter(warehouse__company=company)
        goods_receipts = GoodsReceipt.objects.filter(warehouse__company=company)
        invoices = SupplierInvoice.objects.filter(warehouse__company=company)

        if warehouse_id:
            purchase_orders = purchase_orders.filter(warehouse_id=warehouse_id)
            goods_receipts = goods_receipts.filter(warehouse_id=warehouse_id)
            invoices = invoices.filter(warehouse_id=warehouse_id)

        if date_from:
            purchase_orders = purchase_orders.filter(order_date__gte=date_from)
            goods_receipts = goods_receipts.filter(received_date__gte=date_from)
            invoices = invoices.filter(invoice_date__gte=date_from)
        if date_to:
            purchase_orders = purchase_orders.filter(order_date__lte=date_to)
            goods_receipts = goods_receipts.filter(received_date__lte=date_to)
            invoices = invoices.filter(invoice_date__lte=date_to)

        trunc = PurchasingOverviewService._trunc_function(interval)
        today = timezone.localdate()

        overdue_scope = purchase_orders.filter(
            status__in=OVERDUE_PO_STATUSES,
            expected_delivery_date__lt=today,
        )

        return {
            "date_from": date_from,
            "date_to": date_to,
            "warehouse_id": warehouse_id,
            "interval": interval,
            "po_value": PurchasingOverviewService._period_rows(
                purchase_orders,
                trunc("order_date"),
                {"total_value": Sum("total_amount"), "count": Count("id")},
            ),
            "grns_approved": PurchasingOverviewService._period_rows(
                goods_receipts.filter(status="Approved"),
                trunc("received_date"),
                {"count": Count("id")},
            ),
            "supplier_invoices_approved": PurchasingOverviewService._period_rows(
                invoices.filter(status="Approved"),
                trunc("invoice_date"),
                {"total_value": Sum("total_amount"), "count": Count("id")},
            ),
            "supplier_invoices_paid": PurchasingOverviewService._period_rows(
                invoices.filter(status="Paid"),
                trunc("invoice_date"),
                {"total_value": Sum("total_amount"), "count": Count("id")},
            ),
            "overdue_pos": PurchasingOverviewService._period_rows(
                overdue_scope,
                trunc("expected_delivery_date"),
                {"total_value": Sum("total_amount"), "count": Count("id")},
            ),
        }

    @staticmethod
    def supplier_performance(
        company,
        *,
        date_from=None,
        date_to=None,
        supplier_id=None,
        limit=10,
    ):
        suppliers = Supplier.objects.filter(company=company)
        if supplier_id:
            suppliers = suppliers.filter(id=supplier_id)

        grn_lines = GoodsReceiptLineItem.objects.filter(
            goods_receipt__warehouse__company=company,
            po_line_item__supplier__company=company,
        ).select_related(
            "goods_receipt",
            "goods_receipt__purchase_order",
            "po_line_item__supplier",
        )
        invoices = SupplierInvoice.objects.filter(
            warehouse__company=company,
            supplier__company=company,
        )

        if date_from:
            grn_lines = grn_lines.filter(goods_receipt__received_date__gte=date_from)
            invoices = invoices.filter(invoice_date__gte=date_from)
        if date_to:
            grn_lines = grn_lines.filter(goods_receipt__received_date__lte=date_to)
            invoices = invoices.filter(invoice_date__lte=date_to)
        if supplier_id:
            grn_lines = grn_lines.filter(po_line_item__supplier_id=supplier_id)
            invoices = invoices.filter(supplier_id=supplier_id)

        exception_map = PurchasingOverviewService._match_exceptions_by_supplier(
            company,
            invoices=invoices,
        )

        grn_rows = (
            grn_lines.values("po_line_item__supplier_id", "po_line_item__supplier__name")
            .annotate(
                total_grns=Count("goods_receipt_id", distinct=True),
                approved_grns=Count(
                    "goods_receipt_id",
                    filter=Q(goods_receipt__status="Approved"),
                    distinct=True,
                ),
                rejected_grns=Count(
                    "goods_receipt_id",
                    filter=Q(goods_receipt__status="Rejected"),
                    distinct=True,
                ),
                on_time_grns=Count(
                    "goods_receipt_id",
                    filter=Q(
                        goods_receipt__status="Approved",
                        goods_receipt__purchase_order__expected_delivery_date__isnull=False,
                        goods_receipt__received_date__lte=F(
                            "goods_receipt__purchase_order__expected_delivery_date"
                        ),
                    ),
                    distinct=True,
                ),
                approved_with_due_date=Count(
                    "goods_receipt_id",
                    filter=Q(
                        goods_receipt__status="Approved",
                        goods_receipt__purchase_order__expected_delivery_date__isnull=False,
                    ),
                    distinct=True,
                ),
            )
            .order_by("po_line_item__supplier__name")
        )

        rows_by_supplier = {
            row["po_line_item__supplier_id"]: row for row in grn_rows
        }
        average_lead_times = PurchasingOverviewService._average_lead_times(grn_lines)

        results = []
        for supplier in suppliers:
            grn_row = rows_by_supplier.get(supplier.id, {})
            approved_with_due_date = grn_row.get("approved_with_due_date") or 0
            on_time = grn_row.get("on_time_grns") or 0
            exceptions = exception_map.get(
                supplier.id,
                {
                    "price_variance_lines": 0,
                    "quantity_variance_lines": 0,
                    "unmatched_lines": 0,
                    "invoices_with_exceptions": 0,
                },
            )

            if approved_with_due_date:
                on_time_rate = on_time / approved_with_due_date * 100
            else:
                on_time_rate = None

            total_exception_lines = (
                exceptions["price_variance_lines"]
                + exceptions["quantity_variance_lines"]
                + exceptions["unmatched_lines"]
            )
            results.append(
                {
                    "supplier_id": supplier.id,
                    "supplier_name": supplier.name,
                    "rating": supplier.rating,
                    "on_hold": supplier.on_hold,
                    "is_active": supplier.is_active,
                    "total_grns": grn_row.get("total_grns") or 0,
                    "approved_grns": grn_row.get("approved_grns") or 0,
                    "rejected_grns": grn_row.get("rejected_grns") or 0,
                    "on_time_delivery_rate": on_time_rate,
                    "average_lead_time_days": average_lead_times.get(supplier.id),
                    "price_variance_lines": exceptions["price_variance_lines"],
                    "quantity_variance_lines": exceptions["quantity_variance_lines"],
                    "unmatched_lines": exceptions["unmatched_lines"],
                    "invoices_with_exceptions": exceptions["invoices_with_exceptions"],
                    "total_exception_lines": total_exception_lines,
                }
            )

        best_suppliers = sorted(
            results,
            key=lambda row: (
                (
                    row["on_time_delivery_rate"]
                    if row["on_time_delivery_rate"] is not None
                    else -1
                ),
                -row["total_exception_lines"],
                -(row["rating"] or 0),
            ),
            reverse=True,
        )[:limit]
        worst_suppliers = sorted(
            results,
            key=lambda row: (
                row["total_exception_lines"],
                row["rejected_grns"],
                -(row["on_time_delivery_rate"] or 0),
            ),
            reverse=True,
        )[:limit]

        return {
            "date_from": date_from,
            "date_to": date_to,
            "supplier_id": supplier_id,
            "suppliers": results,
            "best_suppliers": best_suppliers,
            "worst_suppliers": worst_suppliers,
        }

    @staticmethod
    def match_exception_summary(company, *, warehouse_id=None):
        invoices = SupplierInvoice.objects.filter(
            warehouse__company=company,
            status__in=NON_EXCEPTION_INVOICE_STATUSES,
        )
        if warehouse_id:
            invoices = invoices.filter(warehouse_id=warehouse_id)
        return PurchasingOverviewService._summarize_match_exceptions(company, invoices)

    @staticmethod
    def _count_by_status(queryset, statuses):
        counts = {
            row["status"]: row["count"]
            for row in queryset.values("status").annotate(count=Count("id"))
        }
        return {status: counts.get(status, 0) for status in statuses}

    @staticmethod
    def _trunc_function(interval):
        if interval == "day":
            return TruncDay
        if interval == "week":
            return TruncWeek
        return TruncMonth

    @staticmethod
    def _period_rows(queryset, period_expression, aggregations):
        rows = (
            queryset.annotate(period=period_expression)
            .values("period")
            .annotate(**aggregations)
            .order_by("period")
        )
        return list(rows)

    @staticmethod
    def _average_lead_times(grn_lines):
        lead_times = {}
        seen = set()
        completed_lines = grn_lines.filter(goods_receipt__status="Approved")

        for line in completed_lines:
            supplier_id = line.po_line_item.supplier_id
            grn = line.goods_receipt
            key = (supplier_id, grn.id)
            if key in seen:
                continue
            seen.add(key)
            days = (grn.received_date - grn.purchase_order.order_date).days
            lead_times.setdefault(supplier_id, []).append(days)

        return {
            supplier_id: sum(days) / len(days)
            for supplier_id, days in lead_times.items()
            if days
        }

    @staticmethod
    def _summarize_match_exceptions(company, invoices):
        result = PurchasingOverviewService._match_exception_rows(company, invoices)
        invoice_ids = set()
        for line in result["exception_lines"]:
            invoice_ids.add(line["invoice_id"])
        return {
            "price_variance_lines": result["price_variance_lines"],
            "quantity_variance_lines": result["quantity_variance_lines"],
            "unmatched_lines": result["unmatched_lines"],
            "invoices_with_exceptions": len(invoice_ids),
            "checked_invoices": invoices.count(),
        }

    @staticmethod
    def _match_exceptions_by_supplier(company, *, invoices):
        result = PurchasingOverviewService._match_exception_rows(company, invoices)
        summary = {}
        invoice_sets = {}

        for line in result["exception_lines"]:
            supplier_id = line["supplier_id"]
            if supplier_id not in summary:
                summary[supplier_id] = {
                    "price_variance_lines": 0,
                    "quantity_variance_lines": 0,
                    "unmatched_lines": 0,
                    "invoices_with_exceptions": 0,
                }
                invoice_sets[supplier_id] = set()

            if line["type"] == "price":
                summary[supplier_id]["price_variance_lines"] += 1
            elif line["type"] == "quantity":
                summary[supplier_id]["quantity_variance_lines"] += 1
            elif line["type"] == "unmatched":
                summary[supplier_id]["unmatched_lines"] += 1
            invoice_sets[supplier_id].add(line["invoice_id"])

        for supplier_id, invoices_with_exceptions in invoice_sets.items():
            summary[supplier_id]["invoices_with_exceptions"] = len(
                invoices_with_exceptions
            )

        return summary

    @staticmethod
    def _match_exception_rows(company, invoices):
        try:
            config = PurchasingConfig.objects.get(company=company)
            price_tolerance = config.price_tolerance_pct / Decimal("100")
            quantity_tolerance = config.qty_tolerance_pct / Decimal("100")
        except PurchasingConfig.DoesNotExist:
            price_tolerance = Decimal("0")
            quantity_tolerance = Decimal("0")

        lines = (
            SupplierInvoiceLineItem.objects.filter(supplier_invoice__in=invoices)
            .select_related(
                "supplier_invoice",
                "gr_line_item",
                "gr_line_item__po_line_item",
            )
            .only(
                "id",
                "supplier_invoice_id",
                "supplier_invoice__supplier_id",
                "quantity_invoiced",
                "unit_price",
                "gr_line_item_id",
                "gr_line_item__quantity_received",
                "gr_line_item__unit_price",
                "gr_line_item__po_line_item_id",
                "gr_line_item__po_line_item__quantity",
                "gr_line_item__po_line_item__unit_price",
            )
        )

        price_variance_lines = 0
        quantity_variance_lines = 0
        unmatched_lines = 0
        exception_lines = []

        for line in lines:
            gr_line = line.gr_line_item
            po_line = gr_line.po_line_item if gr_line else None

            if not gr_line or not po_line:
                unmatched_lines += 1
                exception_lines.append(
                    PurchasingOverviewService._exception_line(line, "unmatched")
                )
                continue

            price_ok = PurchasingOverviewService._within_tolerance(
                line.unit_price, po_line.unit_price, price_tolerance
            ) and PurchasingOverviewService._within_tolerance(
                line.unit_price, gr_line.unit_price, price_tolerance
            )
            quantity_ok = PurchasingOverviewService._within_tolerance(
                line.quantity_invoiced,
                gr_line.quantity_received,
                quantity_tolerance,
            )

            if not price_ok:
                price_variance_lines += 1
                exception_lines.append(
                    PurchasingOverviewService._exception_line(line, "price")
                )
            if not quantity_ok:
                quantity_variance_lines += 1
                exception_lines.append(
                    PurchasingOverviewService._exception_line(line, "quantity")
                )

        return {
            "price_variance_lines": price_variance_lines,
            "quantity_variance_lines": quantity_variance_lines,
            "unmatched_lines": unmatched_lines,
            "exception_lines": exception_lines,
        }

    @staticmethod
    def _exception_line(line, exception_type):
        return {
            "type": exception_type,
            "invoice_id": line.supplier_invoice_id,
            "supplier_id": line.supplier_invoice.supplier_id,
        }

    @staticmethod
    def _within_tolerance(actual, expected, tolerance):
        if expected == 0:
            return actual == 0
        return abs(actual - expected) / expected <= tolerance
