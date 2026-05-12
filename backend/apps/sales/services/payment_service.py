"""
PaymentService — records money received against an invoice.

Rules:
  - Invoice must be in issued, partially_paid, or overdue status.
  - Amount must be > 0.
  - Overpayment is flagged and blocked — requires explicit confirmation.
  - After each payment, invoice status is recomputed.
    - Delegates finance journal posting and AR reconciliation to ARService.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import BankAccount
from apps.finance.services.ar_service import ARService
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
        bank_account_id=None,
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

        bank_account = PaymentService._resolve_bank_account(invoice, bank_account_id)

        payment = Payment(
            invoice=invoice,
            customer=invoice.sales_order.customer,
            amount=amount,
            payment_method=payment_method,
            bank_account=bank_account,
            payment_date=timezone.now(),
            reference=reference,
            received_by=received_by,
            notes=notes,
        )
        payment.save()

        # Ensure AR exists for older invoices and keep finance ledger in sync.
        ar_record = (
            invoice.ar_record
            if hasattr(invoice, "ar_record")
            else ARService.create_from_invoice(
                invoice=invoice,
                created_by=received_by,
            )
        )
        ARService.record_payment(
            ar=ar_record,
            amount=amount,
            payment_method=payment_method,
            received_by=received_by,
            reference=reference,
            notes=notes,
            payment_date=payment.payment_date,
            sales_payment=payment,
            bank_account=bank_account,
            create_finance_payment=True,
        )

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
    def _resolve_bank_account(invoice: Invoice, bank_account_id):
        if not bank_account_id:
            return None

        company = invoice.sales_order.warehouse.company
        try:
            return BankAccount.objects.get(
                pk=bank_account_id,
                company=company,
                is_active=True,
            )
        except BankAccount.DoesNotExist as exc:
            raise ValidationError(
                "Selected bank_account was not found or is inactive for this company.",
                code="invalid_bank_account",
            ) from exc
