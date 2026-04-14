from django.db.models.signals import post_save
from django.dispatch import receiver

from central.models import Company

from .models import ACCOUNT_AP, ACCOUNT_BANK, ACCOUNT_INVENTORY, Account

DEFAULT_ACCOUNTS = [
    (ACCOUNT_BANK, "Bank", "Asset"),
    (ACCOUNT_INVENTORY, "Inventory", "Asset"),
    (ACCOUNT_AP, "Accounts Payable", "Liability"),
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
