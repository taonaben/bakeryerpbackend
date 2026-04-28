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
        "code": "1001", "name": "Cash", "account_type": "asset",
        "account_subtype": "current_asset", "normal_balance": "debit",
        "system_key": SYSTEM_KEY_CASH,
    },
    {
        "code": "1100", "name": "Bank", "account_type": "asset",
        "account_subtype": "current_asset", "normal_balance": "debit",
        "system_key": "BANK",
    },
    {
        "code": "1200", "name": "Raw Materials Inventory", "account_type": "asset",
        "account_subtype": "current_asset", "normal_balance": "debit",
        "system_key": SYSTEM_KEY_INVENTORY_RAW,
    },
    {
        "code": "1210", "name": "Finished Goods Inventory", "account_type": "asset",
        "account_subtype": "current_asset", "normal_balance": "debit",
        "system_key": SYSTEM_KEY_INVENTORY_FG,
    },
    {
        "code": "1220", "name": "Work In Progress", "account_type": "asset",
        "account_subtype": "current_asset", "normal_balance": "debit",
        "system_key": SYSTEM_KEY_WIP,
    },
    {
        "code": "1300", "name": "Accounts Receivable", "account_type": "asset",
        "account_subtype": "current_asset", "normal_balance": "debit",
        "system_key": SYSTEM_KEY_AR,
    },
    {
        "code": "2100", "name": "Accounts Payable", "account_type": "liability",
        "account_subtype": "current_liability", "normal_balance": "credit",
        "system_key": SYSTEM_KEY_AP,
    },
    {
        "code": "4000", "name": "Sales Revenue", "account_type": "revenue",
        "account_subtype": "operating_revenue", "normal_balance": "credit",
        "system_key": SYSTEM_KEY_REVENUE,
    },
    {
        "code": "5000", "name": "Cost of Goods Sold", "account_type": "expense",
        "account_subtype": "cost_of_sales", "normal_balance": "debit",
        "system_key": SYSTEM_KEY_COGS,
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
            # Keep legacy Account table in sync
            Account.objects.get_or_create(
                company=company,
                code=spec["code"],
                defaults={"name": spec["name"], "account_type": spec["account_type"].capitalize()},
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
        return ChartOfAccounts.objects.create(company=company, **data)

    @staticmethod
    @transaction.atomic
    def update_account(account: ChartOfAccounts, data: dict) -> ChartOfAccounts:
        if account.is_system_account and "code" in data and data["code"] != account.code:
            raise ValidationError(
                "The code of a system account cannot be changed.", code="system_account_protected"
            )
        for field, value in data.items():
            setattr(account, field, value)
        account.save()
        return account

    @staticmethod
    @transaction.atomic
    def deactivate_account(account: ChartOfAccounts) -> ChartOfAccounts:
        if account.is_system_account:
            raise ValidationError(
                "System accounts cannot be deactivated.", code="system_account_protected"
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
        return account
