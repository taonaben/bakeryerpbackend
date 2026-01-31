from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.inventory"
    label = "inventory"

    def ready(self):
        # Temporarily disable automatic signal imports while debugging deployment failures.
        # from . import signals
        try:
            # Optionally import signals, but swallow import-time errors to allow the app to start.
            from . import signals  # noqa: F401
        except Exception:
            # Avoid crashing the process during startup. Log to console if needed.
            import sys, traceback

            traceback.print_exc(file=sys.stderr)
