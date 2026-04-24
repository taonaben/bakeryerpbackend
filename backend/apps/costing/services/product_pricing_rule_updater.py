"""
ProductPricingRuleUpdater
=========================
Triggered by StandardCostEngine after a new StandardCost is persisted.

Responsibilities:
  1. Get-or-create a ProductPricingRule for the product (with system defaults).
  2. Recompute recommended_selling_price and minimum_selling_price.
  3. Update standard_cost_reference to the new StandardCost.
  4. Flag any CustomerProduct prices that now fall below the new floor.
"""

from decimal import Decimal, InvalidOperation
from django.db import transaction

from apps.costing.models import ProductPricingRule, StandardCost

# System defaults applied when creating a rule for the first time
DEFAULT_TARGET_MARGIN_PCT = Decimal("40.0000")
DEFAULT_MINIMUM_MARGIN_PCT = Decimal("20.0000")

# Account code used for COGS — referenced here so the constant lives in one place
ACCOUNT_COGS = "5100"
ACCOUNT_INVENTORY = "1200"


class ProductPricingRuleUpdater:
    """
    Recompute and persist pricing floors for a product after a new StandardCost.

    Usage::

        updater = ProductPricingRuleUpdater(standard_cost=standard_cost)
        rule = updater.run()
    """

    def __init__(self, standard_cost: StandardCost, updated_by=None):
        self.standard_cost = standard_cost
        self.updated_by = updated_by or standard_cost.computed_by

    @transaction.atomic
    def run(self) -> ProductPricingRule:
        rule = self._get_or_create_rule()
        self._recompute_prices(rule)
        rule.standard_cost_reference = self.standard_cost
        rule.updated_by = self.updated_by
        rule.save()
        self._flag_below_floor_customer_prices(rule)
        return rule

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _get_or_create_rule(self) -> ProductPricingRule:
        rule, created = ProductPricingRule.objects.get_or_create(
            product=self.standard_cost.product,
            defaults={
                "target_gross_margin_percentage": DEFAULT_TARGET_MARGIN_PCT,
                "minimum_margin_percentage": DEFAULT_MINIMUM_MARGIN_PCT,
                "currency": self.standard_cost.currency,
                "updated_by": self.updated_by,
            },
        )
        return rule

    def _recompute_prices(self, rule: ProductPricingRule):
        cost = self.standard_cost.total_standard_cost_per_unit

        try:
            target_divisor = Decimal("1") - (rule.target_gross_margin_percentage / Decimal("100"))
            minimum_divisor = Decimal("1") - (rule.minimum_margin_percentage / Decimal("100"))

            if target_divisor <= 0:
                raise ValueError("Target margin >= 100% produces an invalid price.")
            if minimum_divisor <= 0:
                raise ValueError("Minimum margin >= 100% produces an invalid price.")

            rule.recommended_selling_price = (cost / target_divisor).quantize(Decimal("0.01"))
            rule.minimum_selling_price = (cost / minimum_divisor).quantize(Decimal("0.01"))

        except (InvalidOperation, ZeroDivisionError) as exc:
            raise ValueError(
                f"Could not compute selling prices for product '{self.standard_cost.product.name}': {exc}"
            ) from exc

    def _flag_below_floor_customer_prices(self, rule: ProductPricingRule):
        """
        If a sales/CustomerProduct model exists, flag any prices below the new floor.
        This is a soft flag — prices are never changed automatically.
        """
        if rule.minimum_selling_price is None:
            return

        # Attempt to import the CustomerProduct model; skip gracefully if the
        # sales module is not yet installed or the model doesn't exist.
        try:
            from apps.sales.models import CustomerProduct  # noqa: F401
        except ImportError:
            return

        try:
            updated = CustomerProduct.objects.filter(
                product=self.standard_cost.product,
                unit_price__lt=rule.minimum_selling_price,
            ).exclude(
                pricing_flag="below_floor"
            ).update(pricing_flag="below_floor")

            if updated:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    "ProductPricingRuleUpdater: %d CustomerProduct record(s) for '%s' "
                    "are now below the minimum selling price of %s and have been flagged.",
                    updated,
                    self.standard_cost.product.name,
                    rule.minimum_selling_price,
                )
        except Exception:
            # Sales module may not have the pricing_flag field yet — never block costing
            pass
