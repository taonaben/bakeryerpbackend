from django.db.models.signals import post_save
from django.dispatch import receiver

from central.models import Company
from .models import Account

DEFAULT_ACCOUNTS = [
    ("1001", "Cash", "Asset"),
    ("1100", "Bank", "Asset"),
    ("1200", "Raw Materials Inventory", "Asset"),
    ("1210", "Finished Goods Inventory", "Asset"),
    ("1300", "Accounts Receivable", "Asset"),
    ("2100", "Accounts Payable", "Liability"),
    ("4000", "Sales Revenue", "Revenue"),
    ("5000", "Cost of Goods Sold", "Expense"),
]


@receiver(post_save, sender=Company)
def seed_default_accounts(sender, instance, created, **kwargs):
    if not created:
        return
    for code, name, account_type in DEFAULT_ACCOUNTS:
        Account.objects.get_or_create(
            company=instance,
            code=code,
            defaults={"name": name, "account_type": account_type},
        )
