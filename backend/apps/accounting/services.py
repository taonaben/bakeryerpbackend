from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    ACCOUNT_AP,
    ACCOUNT_BANK,
    ACCOUNT_INVENTORY,
    Account,
    JournalEntry,
    JournalEntryLine,
)

DEFAULT_ACCOUNT_DEFINITIONS = {
    ACCOUNT_BANK: {"name": "Bank", "account_type": "Asset"},
    ACCOUNT_INVENTORY: {"name": "Inventory", "account_type": "Asset"},
    ACCOUNT_AP: {"name": "Accounts Payable", "account_type": "Liability"},
}


def _get_or_create_default_account(company, account_code):
    account = Account.objects.filter(company=company, code=account_code).first()
    if account:
        return account

    default_definition = DEFAULT_ACCOUNT_DEFINITIONS.get(account_code)
    if not default_definition:
        raise ValidationError(
            f"Account code '{account_code}' is not configured for company '{company}'."
        )

    account, _ = Account.objects.get_or_create(
        company=company,
        code=account_code,
        defaults=default_definition,
    )
    return account


def post_journal_entry(
    *,
    company,
    entry_date,
    reference,
    description,
    source_type,
    source_id,
    lines,
    created_by=None,
):
    """
    Create a balanced journal entry with lines.

    ``lines`` is a list of dicts:
        [{"account_code": "2100", "debit": Decimal, "credit": Decimal, "description": ""}]

    Raises ValidationError if debits != credits.
    """
    total_debit = sum(Decimal(str(l.get("debit", 0))) for l in lines)
    total_credit = sum(Decimal(str(l.get("credit", 0))) for l in lines)

    if total_debit != total_credit:
        raise ValidationError(
            f"Journal entry is unbalanced: debits={total_debit}, credits={total_credit}"
        )

    if total_debit == 0:
        raise ValidationError("Journal entry must have a non-zero amount.")

    with transaction.atomic():
        resolved_accounts = {}
        for line in lines:
            account_code = line.get("account_code")
            if not account_code:
                raise ValidationError("Each journal entry line must include an account_code.")
            if account_code not in resolved_accounts:
                resolved_accounts[account_code] = _get_or_create_default_account(
                    company, account_code
                )

        entry = JournalEntry.objects.create(
            company=company,
            entry_date=entry_date,
            reference=reference,
            description=description,
            source_type=source_type,
            source_id=source_id,
            created_by=created_by,
        )

        entry_lines = []
        for line in lines:
            account = resolved_accounts[line["account_code"]]
            entry_lines.append(
                JournalEntryLine(
                    journal_entry=entry,
                    account=account,
                    debit=Decimal(str(line.get("debit", 0))),
                    credit=Decimal(str(line.get("credit", 0))),
                    description=line.get("description", ""),
                )
            )

        JournalEntryLine.objects.bulk_create(entry_lines)

        return entry
