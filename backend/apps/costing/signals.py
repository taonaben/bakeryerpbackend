"""
Costing signals
===============
Connects Django model signals to the costing service engines.

  Formula.status → "active"          →  StandardCostEngine
  ProductionBatch.status → "completed" →  CostingEngine
"""

import logging
from django.db.models.signals import pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender="formulation.Formula")
def on_formula_activated(sender, instance, **kwargs):
    """
    Fire StandardCostEngine when a Formula transitions to 'active'.
    Blocks the save and raises if no OverheadRate or unpriced ingredient exists.
    """
    if not instance.pk:
        return  # new object — no previous state to compare

    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if previous.status != "active" and instance.status == "active":
        from apps.costing.services.standard_cost_engine import (
            WarehouseStandardCostEngine,
            StandardCostEngine,
            NoOverheadRateError,
            NoPricedIngredientError,
        )

        # Attempt to find a warehouse from a linked production order
        warehouse = _resolve_warehouse_for_formula(instance)

        try:
            if warehouse:
                engine = WarehouseStandardCostEngine(
                    formula=instance,
                    computed_by=_system_user(),
                    warehouse=warehouse,
                )
            else:
                engine = StandardCostEngine(
                    formula=instance,
                    computed_by=_system_user(),
                )
            engine.run()
        except (NoOverheadRateError, NoPricedIngredientError) as exc:
            # Re-raise as ValidationError so the save is blocked with a clear message
            from django.core.exceptions import ValidationError
            raise ValidationError(str(exc)) from exc
        except Exception as exc:
            logger.error(
                "StandardCostEngine failed for formula %s: %s",
                instance.pk,
                exc,
                exc_info=True,
            )
            raise


@receiver(pre_save, sender="production.ProductionBatch")
def on_batch_completed(sender, instance, **kwargs):
    """
    Fire CostingEngine when a ProductionBatch transitions to 'completed'.
    Errors are logged but do not block the batch save.
    """
    if not instance.pk:
        return

    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if previous.status != "completed" and instance.status == "completed":
        from apps.costing.services.costing_engine import CostingEngine, CostingEngineError

        try:
            engine = CostingEngine(production_batch=instance)
            engine.run()
        except CostingEngineError as exc:
            logger.error(
                "CostingEngine blocked for batch %s: %s",
                instance.batch_number,
                exc,
            )
        except Exception as exc:
            logger.error(
                "CostingEngine unexpected failure for batch %s: %s",
                instance.batch_number,
                exc,
                exc_info=True,
            )


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _resolve_warehouse_for_formula(formula):
    """
    Try to find a warehouse associated with this formula via a production order.
    Returns None if no production order exists yet.
    """
    try:
        order = formula.productionorder_set.select_related("warehouse").first()
        return order.warehouse if order else None
    except Exception:
        return None


def _system_user():
    """
    Return a system/service user for automated computations.
    Falls back to the first superuser if no dedicated service account exists.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.filter(is_active=True, is_superuser=True).first()
    if user is None:
        raise RuntimeError(
            "No active superuser found. Cannot run automated costing without a system user."
        )
    return user
