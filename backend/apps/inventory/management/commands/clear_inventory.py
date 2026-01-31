from django.core.management.base import BaseCommand
from apps.inventory.models import (
    Stock,
    Batch,
    StockMovement,
    StockMovementBatch,
    ProductPolicy,
    InventoryAlert,
)
from central.models import Product


class Command(BaseCommand):
    help = "Clear all inventory data including stocks, batches, movements, policies, alerts, and products"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm the deletion without prompting",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  WARNING: This will delete ALL inventory data including:"
                )
            )
            self.stdout.write("  - Stock records")
            self.stdout.write("  - Batches")
            self.stdout.write("  - Stock Movements")
            self.stdout.write("  - Product Policies")
            self.stdout.write("  - Inventory Alerts")
            self.stdout.write("  - Products")
            self.stdout.write("")

            confirm = "yes"
            if confirm.lower() != "yes":
                self.stdout.write(self.style.ERROR("Deletion cancelled"))
                return

        try:
            # Delete in order of dependencies
            alerts_deleted = InventoryAlert.objects.all().delete()[0]
            self.stdout.write(f"Deleted {alerts_deleted} inventory alerts")

            policies_deleted = ProductPolicy.objects.all().delete()[0]
            self.stdout.write(f"Deleted {policies_deleted} product policies")

            movements_deleted = StockMovement.objects.all().delete()[0]
            self.stdout.write(f"Deleted {movements_deleted} stock movements")

            batches_deleted = Batch.objects.all().delete()[0]
            self.stdout.write(f"Deleted {batches_deleted} batches")

            stocks_deleted = Stock.objects.all().delete()[0]
            self.stdout.write(f"Deleted {stocks_deleted} stock records")

            products_deleted = Product.objects.all().delete()[0]
            self.stdout.write(f"Deleted {products_deleted} products")

            total_deleted = (
                alerts_deleted
                + policies_deleted
                + movements_deleted
                + batches_deleted
                + stocks_deleted
                + products_deleted
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Successfully cleared all inventory data ({total_deleted} records deleted)"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during deletion: {str(e)}"))
