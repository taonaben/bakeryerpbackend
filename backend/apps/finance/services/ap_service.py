"""
APService — manages AccountsPayable lifecycle.

Created automatically when a GRN is confirmed in the purchasing module.
Updated when a supplier payment is recorded.
Never manually created or edited by users.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import (
    BankAccount,
    SYSTEM_KEY_AP,
    SYSTEM_KEY_BANK,
    SYSTEM_KEY_INVENTORY_RAW,
)
from apps.finance.models import AccountsPayable, SupplierPayment
from apps.finance.services.journal_service import JournalLine, JournalService
from apps.purchasing.models import SupplierInvoice


class APService:

    @staticmethod
    @transaction.atomic
    def create_from_supplier_invoice(
        supplier_invoice: SupplierInvoice,
        created_by=None,
    ) -> AccountsPayable:
        """
        Called when a supplier invoice is approved / GRN confirmed.
        Creates the AP record and posts: Debit Inventory, Credit AP.
        """
        if hasattr(supplier_invoice, "ap_record"):
            return supplier_invoice.ap_record  # idempotent

        company = supplier_invoice.warehouse.company

        inventory_account = APService._get_account(
            company, SYSTEM_KEY_INVENTORY_RAW, "1200"
        )
        ap_account = APService._get_account(company, SYSTEM_KEY_AP, "2100")

        je = JournalService.post(
            company=company,
            entry_date=supplier_invoice.invoice_date,
            description=f"Supplier invoice received — {supplier_invoice.invoice_number}",
            lines=[
                JournalLine(
                    account_code=inventory_account.code,
                    type="debit",
                    amount=supplier_invoice.total_amount,
                    description="Inventory received",
                ),
                JournalLine(
                    account_code=ap_account.code,
                    type="credit",
                    amount=supplier_invoice.total_amount,
                    description="AP raised",
                ),
            ],
            reference_type="SupplierInvoice",
            reference_id=supplier_invoice.id,
            created_by=created_by,
        )

        due_date = supplier_invoice.due_date or supplier_invoice.invoice_date

        ap = AccountsPayable.objects.create(
            supplier=supplier_invoice.supplier,
            supplier_invoice=supplier_invoice,
            original_amount=supplier_invoice.total_amount,
            amount_paid=Decimal("0"),
            amount_outstanding=supplier_invoice.total_amount,
            due_date=due_date,
            status="open",
            journal_entry=je,
        )
        return ap

    @staticmethod
    @transaction.atomic
    def record_payment(
        ap: AccountsPayable,
        amount: Decimal,
        payment_method: str,
        paid_by,
        bank_account: BankAccount | None = None,
        reference: str = "",
        notes: str = "",
    ) -> SupplierPayment:
        """
        Record a supplier payment.
        Posts: Debit AP, Credit Cash.
        Updates AP balances and status.
        Overpayment is blocked.
        """
        if amount <= Decimal("0"):
            raise ValidationError(
                "Payment amount must be greater than zero.", code="invalid_amount"
            )

        if ap.amount_outstanding <= 0:
            raise ValidationError(
                "This payable is already fully paid.", code="already_paid"
            )

        if amount > ap.amount_outstanding:
            raise ValidationError(
                f"Payment {amount} exceeds outstanding balance {ap.amount_outstanding}.",
                code="overpayment",
            )

        company = ap.supplier_invoice.warehouse.company
        ap_account = APService._get_account(company, SYSTEM_KEY_AP, "2100")
        cash_account = APService._resolve_payment_account(company, bank_account)

        je = JournalService.post(
            company=company,
            entry_date=timezone.now().date(),
            description=f"Supplier payment — {ap.supplier_invoice.invoice_number}",
            lines=[
                JournalLine(
                    account_code=ap_account.code,
                    type="debit",
                    amount=amount,
                    description="AP cleared",
                ),
                JournalLine(
                    account_code=cash_account.code,
                    type="credit",
                    amount=amount,
                    description="Cash paid",
                ),
            ],
            reference_type="AccountsPayable",
            reference_id=ap.id,
            created_by=paid_by,
        )

        payment = SupplierPayment.objects.create(
            accounts_payable=ap,
            amount=amount,
            payment_date=timezone.now(),
            payment_method=payment_method,
            bank_account=bank_account,
            reference=reference,
            journal_entry=je,
            paid_by=paid_by,
            notes=notes,
        )

        ap.amount_paid += amount
        ap.amount_outstanding = ap.original_amount - ap.amount_paid
        ap.status = "paid" if ap.amount_outstanding <= 0 else "partially_paid"
        ap.save(
            update_fields=["amount_paid", "amount_outstanding", "status", "updated_at"]
        )

        return payment

    @staticmethod
    def mark_overdue(company=None) -> int:
        """Mark open/partially_paid AP records past due_date as overdue."""
        today = timezone.now().date()
        qs = AccountsPayable.objects.filter(
            status__in=["open", "partially_paid"],
            due_date__lt=today,
        )
        if company:
            qs = qs.filter(supplier_invoice__warehouse__company=company)
        return qs.update(status="overdue")

    @staticmethod
    def _get_account(company, system_key: str, fallback_code: str):
        """Look up by system_key first, then fall back to an explicit code."""
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

    @staticmethod
    def _resolve_payment_account(company, bank_account: BankAccount | None = None):
        if bank_account:
            if bank_account.company_id != company.id:
                raise ValidationError(
                    "Selected bank_account does not belong to the payable company.",
                    code="invalid_bank_account_company",
                )
            if not bank_account.is_active:
                raise ValidationError(
                    "Selected bank_account is inactive.",
                    code="inactive_bank_account",
                )
            return APService._get_account(
                company,
                SYSTEM_KEY_BANK,
                bank_account.coa_account.code,
            )
        return APService._get_account(company, SYSTEM_KEY_BANK, "1100")
