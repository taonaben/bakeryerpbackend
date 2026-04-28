"""
PaymentService — records money received against an invoice.

Rules:
  - Invoice must be in issued, partially_paid, or overdue status.
  - Amount must be > 0.
  - Overpayment is flagged and blocked — requires explicit confirmation.
  - After each payment, invoice status is recomputed.
  - Posts a cash/AR journal entry on every payment.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import Account, JournalEntry, JournalEntryLine
from apps.sales.models import Invoice, Payment


class OverpaymentError(ValidationError):
    """Raised when a payment would exceed the invoice total."""
    pass


class PaymentService:

    @staticmethod
    @transaction.atomic
    def record_payment(
        invoice: Invoice,
        amount: Decimal,
        payment_method: str,
        received_by,
        reference: str = "",
        notes: str = "",
        allow_overpayment: bool = False,
    ) -> Payment:
        """
        Record a payment against an invoice.

        Raises:
            ValidationError     — invalid invoice status or zero/negative amount
            OverpaymentError    — payment would exceed invoice total
                                  (pass allow_overpayment=True to override)
        """
        PaymentService._validate_invoice_status(invoice)
        PaymentService._validate_amount(amount)

        existing_sum = PaymentService._paid_so_far(invoice)
        projected = existing_sum + amount

        if projected > invoice.total_amount and not allow_overpayment:
            raise OverpaymentError(
                f"Payment of {amount} would exceed the invoice total "
                f"{invoice.total_amount} (already paid: {existing_sum}). "
                "Pass allow_overpayment=True to accept this explicitly.",
                code="overpayment",
            )

        payment = Payment(
            invoice=invoice,
            customer=invoice.sales_order.customer,
            amount=amount,
            payment_method=payment_method,
            payment_date=timezone.now(),
            reference=reference,
            received_by=received_by,
            notes=notes,
        )
        payment.save()

        # Recompute invoice status
        new_sum = existing_sum + amount
        if new_sum >= invoice.total_amount:
            new_status = "paid"
        else:
            new_status = "partially_paid"

        Invoice.objects.filter(pk=invoice.pk).update(status=new_status)
        invoice.status = new_status  # keep in-memory object consistent

        # Update order status when fully paid
        if new_status == "paid":
            invoice.sales_order.status = "paid"
            invoice.sales_order.save(update_fields=["status", "updated_at"])

        # Post journal entry
        PaymentService._post_payment_journal(invoice, payment, received_by)

        return payment

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_invoice_status(invoice: Invoice) -> None:
        allowed = {"issued", "partially_paid", "overdue"}
        if invoice.status not in allowed:
            raise ValidationError(
                f"Cannot record a payment against an invoice with status "
                f"'{invoice.status}'. Allowed statuses: {', '.join(sorted(allowed))}.",
                code="invalid_invoice_status",
            )

    @staticmethod
    def _validate_amount(amount: Decimal) -> None:
        if amount <= Decimal("0"):
            raise ValidationError(
                "Payment amount must be greater than zero.",
                code="invalid_amount",
            )

    @staticmethod
    def _paid_so_far(invoice: Invoice) -> Decimal:
        result = invoice.payments.aggregate(total=Sum("amount"))["total"]
        return result or Decimal("0")

    @staticmethod
    def _post_payment_journal(
        invoice: Invoice,
        payment: Payment,
        received_by,
    ) -> None:
        """
        Debit Cash/Bank account, Credit Accounts Receivable.
        Silently skips if accounts are not configured.
        """
        method_to_account = {
            "cash": "1100",
            "mobile_money": "1100",
            "bank_transfer": "1110",
            "cheque": "1110",
        }
        cash_code = method_to_account.get(payment.payment_method, "1100")

        try:
            company = invoice.sales_order.warehouse.company
            cash_account = Account.objects.get(company=company, code=cash_code)
            ar_account = Account.objects.get(company=company, code="1300")  # AR
        except Account.DoesNotExist:
            return

        je = JournalEntry.objects.create(
            company=company,
            entry_date=timezone.now().date(),
            reference=invoice.invoice_number,
            description=(
                f"Payment received — {invoice.invoice_number} "
                f"({payment.payment_method})"
            ),
            source_type="Payment",
            source_id=payment.id,
            created_by=received_by,
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=cash_account,
            debit=payment.amount,
            credit=Decimal("0"),
            description="Cash/bank received",
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=ar_account,
            debit=Decimal("0"),
            credit=payment.amount,
            description="AR cleared",
        )
