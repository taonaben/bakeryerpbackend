from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Account, JournalEntry, JournalEntryLine


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
            account = Account.objects.get(company=company, code=line["account_code"])
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
