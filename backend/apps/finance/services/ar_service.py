"""
ARService — manages AccountsReceivable lifecycle.

Created automatically when a sales invoice is issued.
Updated automatically when a payment is recorded.
Never manually created or edited by users.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import (
    BankAccount,
    SYSTEM_KEY_AR,
    SYSTEM_KEY_BANK,
    SYSTEM_KEY_CASH,
    SYSTEM_KEY_REVENUE,
)
from apps.finance.models import AccountsReceivable, CustomerPayment
from apps.finance.services.journal_service import JournalLine, JournalService
from apps.sales.models import Invoice as SalesInvoice


class ARService:

    @staticmethod
    @transaction.atomic
    def create_from_invoice(
        invoice: SalesInvoice, created_by=None
    ) -> AccountsReceivable:
        """
        Called when a sales invoice is issued.
        Creates the AR record and posts: Debit AR, Credit Revenue.
        """
        if hasattr(invoice, "ar_record"):
            return invoice.ar_record  # idempotent

        company = invoice.sales_order.warehouse.company

        # Post journal entry first
        ar_account = ARService._get_account(company, SYSTEM_KEY_AR, "1300")
        revenue_account = ARService._get_account(company, SYSTEM_KEY_REVENUE, "4000")

        je = JournalService.post(
            company=company,
            entry_date=invoice.issued_date,
            description=f"Invoice issued — {invoice.invoice_number}",
            lines=[
                JournalLine(
                    account_code=ar_account.code,
                    type="debit",
                    amount=invoice.total_amount,
                    description="AR raised",
                ),
                JournalLine(
                    account_code=revenue_account.code,
                    type="credit",
                    amount=invoice.total_amount,
                    description="Revenue recognised",
                ),
            ],
            reference_type="Invoice",
            reference_id=invoice.id,
            created_by=created_by,
        )

        ar = AccountsReceivable.objects.create(
            customer=invoice.sales_order.customer,
            invoice=invoice,
            original_amount=invoice.total_amount,
            amount_paid=Decimal("0"),
            amount_outstanding=invoice.total_amount,
            due_date=invoice.due_date,
            status="open",
            journal_entry=je,
        )
        return ar

    @staticmethod
    @transaction.atomic
    def record_payment(
        ar: AccountsReceivable,
        amount: Decimal,
        payment_method: str | None = None,
        received_by=None,
        reference: str = "",
        notes: str = "",
        payment_date=None,
        sales_payment=None,
        bank_account: BankAccount | None = None,
        create_finance_payment: bool = False,
    ) -> AccountsReceivable:
        """
        Called when a customer payment is recorded in the sales module.
        Updates AR balances and status.
        Optionally posts Dr Cash/Bank, Cr AR and mirrors a CustomerPayment audit record.
        """
        if amount <= Decimal("0"):
            raise ValidationError(
                "Payment amount must be greater than zero.", code="invalid_amount"
            )

        if amount > ar.amount_outstanding:
            raise ValidationError(
                f"Payment {amount} exceeds outstanding balance {ar.amount_outstanding}.",
                code="overpayment",
            )

        if create_finance_payment:
            if not received_by:
                raise ValidationError(
                    "received_by is required.", code="missing_received_by"
                )
            if not payment_method:
                raise ValidationError(
                    "payment_method is required.", code="missing_payment_method"
                )

            company = ar.invoice.sales_order.warehouse.company
            cash_account = ARService._resolve_payment_account(
                company=company,
                payment_method=payment_method,
                bank_account=bank_account,
            )
            ar_account = ARService._get_account(company, SYSTEM_KEY_AR, "1300")
            posted_at = payment_date or timezone.now()

            je = JournalService.post(
                company=company,
                entry_date=posted_at.date(),
                description=f"Payment received — {ar.invoice.invoice_number} ({payment_method})",
                lines=[
                    JournalLine(
                        account_code=cash_account.code,
                        type="debit",
                        amount=amount,
                        description="Cash/bank received",
                    ),
                    JournalLine(
                        account_code=ar_account.code,
                        type="credit",
                        amount=amount,
                        description="AR cleared",
                    ),
                ],
                reference_type="Payment",
                reference_id=sales_payment.id if sales_payment else ar.invoice.id,
                created_by=received_by,
            )

            if sales_payment:
                CustomerPayment.objects.update_or_create(
                    sales_payment=sales_payment,
                    defaults={
                        "accounts_receivable": ar,
                        "amount": amount,
                        "payment_date": posted_at,
                        "payment_method": payment_method,
                        "bank_account": bank_account,
                        "reference": reference,
                        "journal_entry": je,
                        "received_by": received_by,
                        "notes": notes,
                    },
                )

        ar.amount_paid += amount
        ar.amount_outstanding = ar.original_amount - ar.amount_paid

        if ar.amount_outstanding <= 0:
            ar.status = "paid"
        elif ar.amount_paid > 0:
            ar.status = "partially_paid"

        ar.save(
            update_fields=["amount_paid", "amount_outstanding", "status", "updated_at"]
        )
        return ar

    @staticmethod
    def _cash_account_for_method(payment_method: str) -> tuple[str, str]:
        """Map payment method to system_key and fallback code."""
        if payment_method in {"cash", "mobile_money"}:
            return SYSTEM_KEY_CASH, "1001"
        return SYSTEM_KEY_BANK, "1100"

    @staticmethod
    def _resolve_payment_account(
        company,
        payment_method: str,
        bank_account: BankAccount | None = None,
    ):
        if bank_account:
            if bank_account.company_id != company.id:
                raise ValidationError(
                    "Selected bank_account does not belong to the invoice company.",
                    code="invalid_bank_account_company",
                )
            if not bank_account.is_active:
                raise ValidationError(
                    "Selected bank_account is inactive.",
                    code="inactive_bank_account",
                )
            return ARService._get_account(
                company,
                SYSTEM_KEY_BANK,
                bank_account.coa_account.code,
            )

        cash_key, fallback = ARService._cash_account_for_method(payment_method)
        return ARService._get_account(company, cash_key, fallback)

    @staticmethod
    def mark_overdue(company=None) -> int:
        """
        Mark open/partially_paid AR records whose due_date has passed as overdue.
        Returns count updated. Intended for a scheduled job.
        """
        today = timezone.now().date()
        qs = AccountsReceivable.objects.filter(
            status__in=["open", "partially_paid"],
            due_date__lt=today,
        )
        if company:
            qs = qs.filter(invoice__sales_order__warehouse__company=company)
        return qs.update(status="overdue")

    @staticmethod
    @transaction.atomic
    def reverse_from_invoice(
        invoice: SalesInvoice, reversed_by, reason: str = ""
    ) -> None:
        """Reverse invoice AR posting and close outstanding AR balance for cancelled invoices."""
        if not hasattr(invoice, "ar_record"):
            return

        ar = invoice.ar_record
        if ar.journal_entry and not ar.journal_entry.is_reversed:
            JournalService.reverse(
                original_entry=ar.journal_entry,
                reversed_by=reversed_by,
                reason=f"Cancelled invoice {invoice.invoice_number}. {reason}".strip(),
            )

        ar.amount_outstanding = Decimal("0")
        ar.status = "paid"
        ar.save(update_fields=["amount_outstanding", "status", "updated_at"])

    @staticmethod
    def _get_account(company, system_key: str, fallback_code: str):
        """Look up by system_key first, fall back to code."""
        try:
            return JournalService.get_account(
                company=company,
                system_key=system_key,
                fallback_code=fallback_code,
            )
        except ValidationError as exc:
            raise ValueError(
                f"Account resolution failed for system_key '{system_key}' and "
                f"fallback code '{fallback_code}' in company '{company.name}'. "
                "Ensure the chart of accounts is configured."
            ) from exc
