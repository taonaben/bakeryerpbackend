from django.apps import AppConfig


class CostingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.costing"
    label = "costing"

    def ready(self):
        import apps.costing.signals  # noqa: F401
