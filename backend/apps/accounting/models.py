import uuid

from django.conf import settings
from django.db import models

# ── Default account codes ──────────────────────────────────────
ACCOUNT_BANK = "1100"
ACCOUNT_INVENTORY = "1200"
ACCOUNT_AP = "2100"

from central.models import Company


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
        Company,
        on_delete=models.CASCADE,
        related_name="accounts",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("company", "code")

    def __str__(self):
        return f"{self.code} - {self.name}"


class JournalEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="journal_entries",
    )
    entry_date = models.DateField()
    reference = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    source_type = models.CharField(max_length=50)
    source_id = models.UUIDField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Journal entries"

    def __str__(self):
        return f"{self.reference} ({self.entry_date})"


class JournalEntryLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="journal_lines",
    )
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.account.code} Dr={self.debit} Cr={self.credit}"
