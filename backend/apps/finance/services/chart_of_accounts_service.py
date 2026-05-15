"""
ChartOfAccountsService — manages the chart of accounts.

Rules:
  - System accounts cannot be deleted or have their code changed
  - No hard deletes — deactivate only, and only if no journal lines reference the account
  - System accounts are seeded on first setup
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounting.models import (
    SYSTEM_KEY_AP,
    SYSTEM_KEY_AR,
    SYSTEM_KEY_BANK,
    SYSTEM_KEY_CASH,
    SYSTEM_KEY_COGS,
    SYSTEM_KEY_INVENTORY_FG,
    SYSTEM_KEY_INVENTORY_RAW,
    SYSTEM_KEY_REVENUE,
    SYSTEM_KEY_WIP,
    Account,
    ChartOfAccounts,
)
from central.models import Company

# Default system accounts seeded on first setup
SYSTEM_ACCOUNTS = [
    {
        "code": "1001",
        "name": "Cash",
        "account_type": "asset",
        "account_subtype": "current_asset",
        "normal_balance": "debit",
        "system_key": SYSTEM_KEY_CASH,
    },
    {
        "code": "1100",
        "name": "Bank",
        "account_type": "asset",
        "account_subtype": "current_asset",
        "normal_balance": "debit",
        "system_key": SYSTEM_KEY_BANK,
    },
    {
        "code": "1200",
        "name": "Raw Materials Inventory",
        "account_type": "asset",
        "account_subtype": "current_asset",
        "normal_balance": "debit",
        "system_key": SYSTEM_KEY_INVENTORY_RAW,
    },
    {
        "code": "1210",
        "name": "Finished Goods Inventory",
        "account_type": "asset",
        "account_subtype": "current_asset",
        "normal_balance": "debit",
        "system_key": SYSTEM_KEY_INVENTORY_FG,
    },
    {
        "code": "1220",
        "name": "Work In Progress",
        "account_type": "asset",
        "account_subtype": "current_asset",
        "normal_balance": "debit",
        "system_key": SYSTEM_KEY_WIP,
    },
    {
        "code": "1300",
        "name": "Accounts Receivable",
        "account_type": "asset",
        "account_subtype": "current_asset",
        "normal_balance": "debit",
        "system_key": SYSTEM_KEY_AR,
    },
    {
        "code": "2100",
        "name": "Accounts Payable",
        "account_type": "liability",
        "account_subtype": "current_liability",
        "normal_balance": "credit",
        "system_key": SYSTEM_KEY_AP,
    },
    {
        "code": "4000",
        "name": "Sales Revenue",
        "account_type": "revenue",
        "account_subtype": "operating_revenue",
        "normal_balance": "credit",
        "system_key": SYSTEM_KEY_REVENUE,
    },
    {
        "code": "5000",
        "name": "Cost of Goods Sold",
        "account_type": "expense",
        "account_subtype": "cost_of_sales",
        "normal_balance": "debit",
        "system_key": SYSTEM_KEY_COGS,
    },
    {
        "code": "5200",
        "name": "Wages",
        "account_type": "expense",
        "account_subtype": "operating_expense",
        "normal_balance": "debit",
        "system_key": "WAGES",
    },
    {
        "code": "5300",
        "name": "Overhead",
        "account_type": "expense",
        "account_subtype": "operating_expense",
        "normal_balance": "debit",
        "system_key": "OVERHEAD",
    },
    {
        "code": "3000",
        "name": "Retained Earnings",
        "account_type": "equity",
        "account_subtype": "equity",
        "normal_balance": "credit",
        "system_key": "RETAINED_EARNINGS",
    },
    {
        "code": "4010",
        "name": "Discount Received",
        "account_type": "revenue",
        "account_subtype": "operating_revenue",
        "normal_balance": "credit",
        "system_key": "DISCOUNT_RECEIVED",
    },
    {
        "code": "5400",
        "name": "Discount Allowed",
        "account_type": "expense",
        "account_subtype": "operating_expense",
        "normal_balance": "debit",
        "system_key": "DISCOUNT_ALLOWED",
    },
]


class ChartOfAccountsService:

    @staticmethod
    @transaction.atomic
    def seed_system_accounts(company: Company) -> list[ChartOfAccounts]:
        """
        Seed the default system accounts for a company on first setup.
        Idempotent — skips accounts that already exist.
        Also seeds the legacy Account records used by existing service code.
        """
        created = []
        for spec in SYSTEM_ACCOUNTS:
            coa, _ = ChartOfAccounts.objects.get_or_create(
                company=company,
                code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "account_type": spec["account_type"],
                    "account_subtype": spec["account_subtype"],
                    "normal_balance": spec["normal_balance"],
                    "system_key": spec["system_key"],
                    "is_system_account": True,
                    "is_active": True,
                },
            )
            ChartOfAccountsService._sync_legacy_account(
                company=company,
                code=spec["code"],
                name=spec["name"],
                account_type=spec["account_type"],
            )
            created.append(coa)
        return created

    @staticmethod
    @transaction.atomic
    def create_account(company: Company, data: dict) -> ChartOfAccounts:
        if ChartOfAccounts.objects.filter(company=company, code=data["code"]).exists():
            raise ValidationError(
                f"Account code '{data['code']}' already exists.", code="duplicate_code"
            )
        account = ChartOfAccounts.objects.create(company=company, **data)
        ChartOfAccountsService._sync_legacy_account(
            company=company,
            code=account.code,
            name=account.name,
            account_type=account.account_type,
        )
        return account

    @staticmethod
    @transaction.atomic
    def update_account(account: ChartOfAccounts, data: dict) -> ChartOfAccounts:
        if (
            account.is_system_account
            and "code" in data
            and data["code"] != account.code
        ):
            raise ValidationError(
                "The code of a system account cannot be changed.",
                code="system_account_protected",
            )
        old_code = account.code
        for field, value in data.items():
            setattr(account, field, value)
        account.save()
        ChartOfAccountsService._sync_legacy_account(
            company=account.company,
            code=account.code,
            name=account.name,
            account_type=account.account_type,
            old_code=old_code,
        )
        return account

    @staticmethod
    @transaction.atomic
    def deactivate_account(account: ChartOfAccounts) -> ChartOfAccounts:
        if account.is_system_account:
            raise ValidationError(
                "System accounts cannot be deactivated.",
                code="system_account_protected",
            )
        # Block if journal lines reference this account
        from apps.accounting.models import JournalEntryLine

        if JournalEntryLine.objects.filter(account__code=account.code).exists():
            raise ValidationError(
                "Cannot deactivate an account that has journal entries.",
                code="account_has_entries",
            )
        account.is_active = False
        account.save(update_fields=["is_active"])
        Account.objects.filter(company=account.company, code=account.code).update(
            is_active=False
        )
        return account

    @staticmethod
    def _sync_legacy_account(
        company: Company,
        code: str,
        name: str,
        account_type: str,
        old_code: str | None = None,
    ) -> Account:
        """Keep the legacy Account table aligned with ChartOfAccounts changes."""
        normalized_type = account_type.capitalize()
        lookup_code = old_code or code

        legacy = Account.objects.filter(company=company, code=lookup_code).first()
        if not legacy:
            return Account.objects.create(
                company=company,
                code=code,
                name=name,
                account_type=normalized_type,
                is_active=True,
            )

        update_fields = []
        if legacy.code != code:
            legacy.code = code
            update_fields.append("code")
        if legacy.name != name:
            legacy.name = name
            update_fields.append("name")
        if legacy.account_type != normalized_type:
            legacy.account_type = normalized_type
            update_fields.append("account_type")
        if not legacy.is_active:
            legacy.is_active = True
            update_fields.append("is_active")

        if update_fields:
            legacy.save(update_fields=update_fields + ["updated_at"])
        return legacy
