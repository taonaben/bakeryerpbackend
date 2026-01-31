from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.inventory"
    label = "inventory"

    def ready(self):
        try:
            import apps.inventory.signals.stock_update
            import apps.inventory.signals.stock_alerts
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to import signals: {e}")
