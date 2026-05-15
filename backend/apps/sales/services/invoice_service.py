"""
InvoiceService — generates and manages invoices.

Rules:
  - Invoice totals are computed from dispatched quantities, not ordered quantities.
  - invoice_type is derived from order_type (pos → receipt, b2b → tax_invoice).
  - due_date is computed from customer.payment_terms.
  - Once issued, amounts are immutable — cancel and reissue to correct.
  - Overdue detection is a scheduled job (mark_overdue_invoices).
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.finance.services.ar_service import ARService
from apps.sales.models import Invoice, SalesOrder


class InvoiceService:

    # ------------------------------------------------------------------ #
    # Create                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    @transaction.atomic
    def create_invoice(order: SalesOrder, created_by) -> Invoice:
        """
        Generate an invoice from dispatched lines.

        Totals are based on quantity_dispatched × unit_price, not ordered quantity.
        Status is set to 'issued' immediately.
        """
        if hasattr(order, "invoice"):
            raise ValidationError(
                f"An invoice already exists for order {order.order_number}.",
                code="invoice_already_exists",
            )

        lines = order.lines.all()
        subtotal = sum(
            (ln.quantity_dispatched * ln.unit_price for ln in lines),
            Decimal("0"),
        )
        # Tax placeholder — extend when tax rules are defined
        tax_amount = Decimal("0")
        total_amount = subtotal + tax_amount

        issued_date = timezone.now().date()
        due_date = InvoiceService._compute_due_date(
            issued_date, order.customer.payment_terms
        )

        invoice_type = "receipt" if order.order_type == "pos" else "tax_invoice"

        invoice = Invoice(
            sales_order=order,
            invoice_type=invoice_type,
            issued_date=issued_date,
            due_date=due_date,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            status="issued",
            created_by=created_by,
        )
        invoice.save()

        # Update order status
        order.status = "invoiced"
        order.save(update_fields=["status", "updated_at"])

        # Create finance AR mirror and invoice journal posting.
        ARService.create_from_invoice(invoice=invoice, created_by=created_by)

        return invoice

    # ------------------------------------------------------------------ #
    # Cancel                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    @transaction.atomic
    def cancel_invoice(invoice: Invoice, cancelled_by, reason: str = "") -> Invoice:
        """
        Cancel an issued invoice.

        - Reverses the accounts-receivable journal entry.
        - Keeps the cancelled record — never deletes.
        - Returns the cancelled invoice (caller should create a replacement).
        """
        if invoice.status == "cancelled":
            raise ValidationError(
                "Invoice is already cancelled.",
                code="already_cancelled",
            )
        if invoice.status == "paid":
            raise ValidationError(
                "A fully paid invoice cannot be cancelled directly. "
                "Use a credit note process.",
                code="paid_invoice",
            )

        invoice.status = "cancelled"
        invoice.save(update_fields=["status"])

        ARService.reverse_from_invoice(invoice, cancelled_by, reason)

        return invoice

    # ------------------------------------------------------------------ #
    # Overdue detection (scheduled job)                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def mark_overdue_invoices() -> int:
        """
        Mark all issued/partially_paid invoices whose due_date has passed as overdue.
        Returns the count of invoices updated.
        """
        today = timezone.now().date()
        updated = Invoice.objects.filter(
            status__in=["issued", "partially_paid"],
            due_date__lt=today,
        ).update(status="overdue")
        return updated

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_due_date(issued_date: date, payment_terms: str) -> date:
        if payment_terms == "net_30":
            return issued_date + timedelta(days=30)
        if payment_terms == "net_60":
            return issued_date + timedelta(days=60)
        return issued_date  # cash
