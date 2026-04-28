"""
JournalService — the single point of entry for all journal posting.

Rules enforced here (not in models):
  1. Double entry: debits must equal credits — unbalanced entries are rejected
  2. Period check: entry_date must fall within an open FiscalPeriod
  3. Immutability: entries are never edited; corrections go through reversals
  4. Traceability: every entry carries reference_type + reference_id
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import (
    Account,
    FiscalPeriod,
    JournalEntry,
    JournalEntryLine,
)
from central.models import Company


@dataclass
class JournalLine:
    account_code: str
    type: str          # "debit" or "credit"
    amount: Decimal
    description: str = ""


class JournalService:

    @staticmethod
    @transaction.atomic
    def post(
        company: Company,
        entry_date,
        description: str,
        lines: list[JournalLine],
        reference_type: str = "",
        reference_id: Optional[uuid.UUID] = None,
        entry_type: str = "automated",
        created_by=None,
    ) -> JournalEntry:
        """
        Post a balanced journal entry.

        Raises:
            ValidationError — unbalanced entry, closed/missing period, unknown account
        """
        # 1. Balance check
        debits = sum(l.amount for l in lines if l.type == "debit")
        credits = sum(l.amount for l in lines if l.type == "credit")
        if debits != credits:
            raise ValidationError(
                f"Journal entry is unbalanced: debits={debits}, credits={credits}.",
                code="unbalanced_entry",
            )
        if len(lines) < 2:
            raise ValidationError(
                "A journal entry must have at least two lines.",
                code="insufficient_lines",
            )

        # 2. Fiscal period check
        period = JournalService._resolve_period(company, entry_date)

        # 3. Resolve accounts
        account_map = JournalService._resolve_accounts(company, lines)

        # 4. Create header
        entry = JournalEntry(
            company=company,
            fiscal_period=period,
            entry_date=entry_date,
            entry_type=entry_type,
            reference_type=reference_type,
            reference_id=reference_id,
            reference=str(reference_id) if reference_id else "",
            source_type=reference_type,
            source_id=reference_id,
            description=description,
            is_balanced=True,
            created_by=created_by,
        )
        entry.save()

        # 5. Create lines
        for line in lines:
            account = account_map[line.account_code]
            JournalEntryLine.objects.create(
                journal_entry=entry,
                account=account,
                type=line.type,
                amount=line.amount,
                debit=line.amount if line.type == "debit" else Decimal("0"),
                credit=line.amount if line.type == "credit" else Decimal("0"),
                description=line.description,
            )

        return entry

    @staticmethod
    @transaction.atomic
    def reverse(
        original_entry: JournalEntry,
        reversed_by,
        reason: str = "",
    ) -> JournalEntry:
        """
        Create an equal-and-opposite reversal entry linked to the original.
        The original entry is marked is_reversed=True.
        """
        if original_entry.is_reversed:
            raise ValidationError(
                f"Entry {original_entry.entry_number} has already been reversed.",
                code="already_reversed",
            )

        original_lines = original_entry.lines.all()
        reversal_lines = [
            JournalLine(
                account_code=line.account.code,
                type="credit" if line.type == "debit" else "debit",
                amount=line.amount,
                description=f"Reversal: {line.description}",
            )
            for line in original_lines
        ]

        reversal = JournalService.post(
            company=original_entry.company,
            entry_date=timezone.now().date(),
            description=f"Reversal of {original_entry.entry_number}. {reason}".strip(),
            lines=reversal_lines,
            reference_type=original_entry.reference_type,
            reference_id=original_entry.reference_id,
            entry_type="reversal",
            created_by=reversed_by,
        )

        # Link original → reversal
        original_entry.is_reversed = True
        original_entry.reversed_by = reversal
        original_entry.save(update_fields=["is_reversed", "reversed_by"])

        return reversal

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_period(company: Company, entry_date) -> FiscalPeriod:
        try:
            period = FiscalPeriod.objects.get(
                company=company,
                period_start__lte=entry_date,
                period_end__gte=entry_date,
                status="open",
            )
        except FiscalPeriod.DoesNotExist:
            raise ValidationError(
                f"No open fiscal period found for date {entry_date}. "
                "Create or open a fiscal period before posting.",
                code="no_open_period",
            )
        return period

    @staticmethod
    def _resolve_accounts(company: Company, lines: list[JournalLine]) -> dict:
        codes = {line.account_code for line in lines}
        accounts = Account.objects.filter(company=company, code__in=codes, is_active=True)
        account_map = {a.code: a for a in accounts}
        missing = codes - set(account_map.keys())
        if missing:
            raise ValidationError(
                f"Account code(s) not found or inactive: {', '.join(sorted(missing))}.",
                code="unknown_account",
            )
        return account_map
