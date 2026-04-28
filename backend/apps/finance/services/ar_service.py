"""
ARService — manages AccountsReceivable lifecycle.

Created automatically when a sales invoice is issued.
Updated automatically when a payment is recorded.
Never manually created or edited by users.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounting.models import SYSTEM_KEY_AR, SYSTEM_KEY_REVENUE, ChartOfAccounts
from apps.finance.models import AccountsReceivable
from apps.finance.services.journal_service import JournalLine, JournalService
from apps.sales.models import Invoice as SalesInvoice


class ARService:

    @staticmethod
    @transaction.atomic
    def create_from_invoice(invoice: SalesInvoice, created_by=None) -> AccountsReceivable:
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
                JournalLine(account_code=ar_account.code, type="debit",
                            amount=invoice.total_amount, description="AR raised"),
                JournalLine(account_code=revenue_account.code, type="credit",
                            amount=invoice.total_amount, description="Revenue recognised"),
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
    def record_payment(ar: AccountsReceivable, amount: Decimal) -> AccountsReceivable:
        """
        Called when a customer payment is recorded in the sales module.
        Updates AR balances and status. Journal entry is posted by PaymentService.
        """
        ar.amount_paid += amount
        ar.amount_outstanding = ar.original_amount - ar.amount_paid

        if ar.amount_outstanding <= 0:
            ar.status = "paid"
        elif ar.amount_paid > 0:
            ar.status = "partially_paid"

        ar.save(update_fields=["amount_paid", "amount_outstanding", "status", "updated_at"])
        return ar

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
    def _get_account(company, system_key: str, fallback_code: str):
        """Look up by system_key first, fall back to code."""
        from apps.accounting.models import Account
        try:
            return Account.objects.get(company=company, code=fallback_code, is_active=True)
        except Account.DoesNotExist:
            raise ValueError(
                f"Account with code '{fallback_code}' not found for company '{company.name}'. "
                "Ensure the chart of accounts is configured."
            )
