import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from central.models import Company

# ── Well-known system account keys ────────────────────────────────────────
# Other modules reference these constants, not raw codes, so renaming an
# account in the chart never breaks the integration.
SYSTEM_KEY_CASH = "CASH"
SYSTEM_KEY_BANK = "BANK"
SYSTEM_KEY_AR = "AR"
SYSTEM_KEY_AP = "AP"
SYSTEM_KEY_INVENTORY_RAW = "INVENTORY_RAW"
SYSTEM_KEY_INVENTORY_FG = "INVENTORY_FG"
SYSTEM_KEY_REVENUE = "REVENUE"
SYSTEM_KEY_COGS = "COGS"
SYSTEM_KEY_WIP = "WIP"


class FiscalPeriod(models.Model):
    """
    Defines the accounting calendar. Every JournalEntry belongs to a period.
    Once closed, no entry can be posted into it — enforced at posting time.
    """

    STATUS_CHOICES = [("open", "Open"), ("closed", "Closed")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="fiscal_periods"
    )
    name = models.CharField(max_length=100)  # e.g. "January 2025"
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_fiscal_periods",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fiscal Period"
        verbose_name_plural = "Fiscal Periods"
        ordering = ["period_start"]
        indexes = [
            models.Index(fields=["company", "status"], name="fp_company_status_idx"),
            models.Index(
                fields=["company", "period_start"], name="fp_company_start_idx"
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"


class ChartOfAccounts(models.Model):
    """
    Master list of every financial bucket in the system.
    System accounts are seeded on setup and cannot be deleted or have their code changed.
    """

    ACCOUNT_TYPE_CHOICES = [
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("equity", "Equity"),
        ("revenue", "Revenue"),
        ("expense", "Expense"),
    ]

    ACCOUNT_SUBTYPE_CHOICES = [
        ("current_asset", "Current Asset"),
        ("fixed_asset", "Fixed Asset"),
        ("current_liability", "Current Liability"),
        ("long_term_liability", "Long-Term Liability"),
        ("equity", "Equity"),
        ("operating_revenue", "Operating Revenue"),
        ("cost_of_sales", "Cost of Sales"),
        ("operating_expense", "Operating Expense"),
    ]

    NORMAL_BALANCE_CHOICES = [("debit", "Debit"), ("credit", "Credit")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="chart_of_accounts"
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    account_subtype = models.CharField(
        max_length=30, choices=ACCOUNT_SUBTYPE_CHOICES, blank=True
    )
    normal_balance = models.CharField(max_length=6, choices=NORMAL_BALANCE_CHOICES)
    # Internal key used by other modules — stable even if code/name changes
    system_key = models.CharField(max_length=50, blank=True, db_index=True)
    is_system_account = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Chart of Accounts"
        verbose_name_plural = "Chart of Accounts"
        unique_together = [("company", "code")]
        indexes = [
            models.Index(
                fields=["company", "account_type"], name="coa_company_type_idx"
            ),
            models.Index(
                fields=["company", "is_active"], name="coa_company_active_idx"
            ),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


# ── Keep the legacy Account model as an alias so existing FK references
# in other apps (costing, sales, dispatch) continue to work unchanged.
# New code should use ChartOfAccounts directly.
class Account(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ("Asset", "Asset"),
        ("Liability", "Liability"),
        ("Equity", "Equity"),
        ("Revenue", "Revenue"),
        ("Expense", "Expense"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="accounts"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("company", "code")

    def __str__(self):
        return f"{self.code} - {self.name}"


class BankAccount(models.Model):
    """Represents a physical cash/bank account mapped to a ledger account."""

    ACCOUNT_TYPE_CHOICES = [
        ("current", "Current"),
        ("savings", "Savings"),
        ("cash", "Cash"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="bank_accounts",
    )
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    currency = models.CharField(max_length=3)
    coa_account = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.PROTECT,
        related_name="bank_accounts",
    )
    current_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0")
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bank Account"
        verbose_name_plural = "Bank Accounts"
        indexes = [
            models.Index(fields=["company", "is_active"], name="ba_company_active_idx"),
            models.Index(
                fields=["company", "currency"], name="ba_company_currency_idx"
            ),
        ]

    def clean(self):
        if self.coa_account and self.coa_account.company_id != self.company_id:
            raise ValidationError("coa_account must belong to the same company.")

    def __str__(self):
        return f"{self.name} ({self.currency})"


class JournalEntry(models.Model):
    """
    Header for every financial event. Immutable after creation.
    Automated entries are created by other modules; manual entries by finance staff.
    """

    ENTRY_TYPE_CHOICES = [
        ("automated", "Automated"),
        ("manual", "Manual"),
        ("reversal", "Reversal"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="journal_entries"
    )
    entry_number = models.CharField(
        max_length=20, unique=True, editable=False, null=True, blank=True
    )
    fiscal_period = models.ForeignKey(
        FiscalPeriod,
        on_delete=models.PROTECT,
        related_name="journal_entries",
        null=True,
        blank=True,  # resolved at posting time
    )
    entry_date = models.DateField()
    entry_type = models.CharField(
        max_length=10, choices=ENTRY_TYPE_CHOICES, default="automated"
    )
    # Source traceability
    reference_type = models.CharField(max_length=50, blank=True)  # e.g. "SalesOrder"
    reference_id = models.UUIDField(null=True, blank=True)
    # Legacy field — kept for backward compat with existing service code
    reference = models.CharField(max_length=100, blank=True)
    source_type = models.CharField(max_length=50, blank=True)
    source_id = models.UUIDField(null=True, blank=True)
    description = models.TextField()
    is_balanced = models.BooleanField(default=False)
    is_reversed = models.BooleanField(default=False)
    reversed_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reverses",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Journal Entry"
        verbose_name_plural = "Journal Entries"
        ordering = ["-entry_date", "-created_at"]
        indexes = [
            models.Index(fields=["company", "entry_date"], name="je_company_date_idx"),
            models.Index(fields=["reference_type", "reference_id"], name="je_ref_idx"),
            models.Index(fields=["fiscal_period"], name="je_period_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.entry_number:
            from apps.accounting.utils import generate_entry_number

            self.entry_number = generate_entry_number(self.company)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.entry_number} ({self.entry_date})"


class JournalEntryLine(models.Model):
    """
    Individual debit/credit lines. Minimum two per entry.
    Immutable after creation — no updates, no deletes.
    """

    LINE_TYPE_CHOICES = [("debit", "Debit"), ("credit", "Credit")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.CASCADE, related_name="lines"
    )
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="journal_lines"
    )
    type = models.CharField(max_length=6, choices=LINE_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    # Legacy debit/credit fields — kept for backward compat
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Journal Entry Line"
        verbose_name_plural = "Journal Entry Lines"

    def __str__(self):
        return f"{self.journal_entry.entry_number} | {self.account.code} {self.type} {self.amount}"
