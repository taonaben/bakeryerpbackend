"""
FiscalPeriodService — manages the accounting calendar.

Rules:
  - Periods cannot overlap within a company
  - Once closed, a period cannot be reopened
  - Closing a period marks it permanently — corrections post into the current open period
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import FiscalPeriod
from central.models import Company


class FiscalPeriodService:

    @staticmethod
    @transaction.atomic
    def create_period(
        company: Company,
        name: str,
        period_start,
        period_end,
        created_by=None,
    ) -> FiscalPeriod:
        """Create a new open fiscal period. Rejects overlapping periods."""
        FiscalPeriodService._check_overlap(company, period_start, period_end)

        if period_end < period_start:
            raise ValidationError(
                "period_end must be on or after period_start.",
                code="invalid_date_range",
            )

        return FiscalPeriod.objects.create(
            company=company,
            name=name,
            period_start=period_start,
            period_end=period_end,
            status="open",
        )

    @staticmethod
    @transaction.atomic
    def close_period(period: FiscalPeriod, closed_by) -> FiscalPeriod:
        """
        Close a fiscal period. Irreversible.
        After closing, no journal entry can be posted with a date inside this period.
        """
        if period.status == "closed":
            raise ValidationError(
                f"Period '{period.name}' is already closed.",
                code="already_closed",
            )

        period.status = "closed"
        period.closed_at = timezone.now()
        period.closed_by = closed_by
        period.save(update_fields=["status", "closed_at", "closed_by"])
        return period

    @staticmethod
    def _check_overlap(company: Company, period_start, period_end, exclude_id=None):
        qs = FiscalPeriod.objects.filter(
            company=company,
            period_start__lte=period_end,
            period_end__gte=period_start,
        )
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise ValidationError(
                "The specified date range overlaps with an existing fiscal period.",
                code="period_overlap",
            )
