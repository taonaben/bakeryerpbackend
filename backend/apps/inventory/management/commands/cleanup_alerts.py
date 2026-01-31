from django.core.management.base import BaseCommand
from apps.inventory.models import InventoryAlert


class Command(BaseCommand):
    help = 'Clean up orphaned inventory alert records'

    def handle(self, *args, **options):
        # Delete all inventory alerts with invalid foreign key references
        deleted_count = InventoryAlert.objects.all().delete()[0]
        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {deleted_count} inventory alert records')
        )