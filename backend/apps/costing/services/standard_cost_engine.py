"""
StandardCostEngine
==================
Triggered when a Formula's status transitions to "active".

Responsibilities:
  1. Resolve the active OverheadRate for the formula's warehouse + today.
  2. Filter formula lines to MATERIAL type only.
  3. Resolve preferred (or cheapest) supplier price per ingredient.
  4. Compute per-unit material cost, overhead cost, and totals.
  5. Persist StandardCost + StandardCostLine records (immutable — never overwritten).
  6. Cascade to ProductPricingRuleUpdater.
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.costing.models import StandardCost, StandardCostLine, OverheadRate
from apps.purchasing.models import SupplierProduct


class NoPricedIngredientError(Exception):
    """Raised when a MATERIAL formula line has no supplier price."""


class NoOverheadRateError(Exception):
    """Raised when no active OverheadRate covers the current date for the warehouse."""


class StandardCostEngine:
    """
    Compute and persist a StandardCost for a given Formula.

    Usage::

        engine = StandardCostEngine(formula=formula, computed_by=request.user)
        standard_cost = engine.run()
    """

    def __init__(self, formula, computed_by):
        self.formula = formula
        self.computed_by = computed_by

    # ------------------------------------------------------------------ #
    #  Public entry point                                                  #
    # ------------------------------------------------------------------ #

    @transaction.atomic
    def run(self) -> StandardCost:
        """
        Execute the full standard-cost computation.

        Returns the newly created StandardCost.
        Raises NoOverheadRateError or NoPricedIngredientError on failure.
        """
        # Guard: never overwrite an existing standard cost for this formula revision
        existing = StandardCost.objects.filter(formula=self.formula).first()
        if existing:
            return existing

        overhead_rate = self._resolve_overhead_rate()
        material_lines = self._material_lines()
        line_costs = self._compute_line_costs(material_lines)

        total_material_cost_per_batch = sum(lc["cost_per_batch"] for lc in line_costs)
        effective_units = Decimal(str(self.formula.batch_size)) * (
            Decimal(str(self.formula.yield_percentage)) / Decimal("100")
        )
        material_cost_per_unit = total_material_cost_per_batch / effective_units
        overhead_cost_per_unit = overhead_rate.rate_per_unit
        total_standard_cost_per_unit = material_cost_per_unit + overhead_cost_per_unit

        standard_cost = StandardCost.objects.create(
            formula=self.formula,
            product=self.formula.product,
            overhead_rate=overhead_rate,
            material_cost_per_unit=material_cost_per_unit,
            overhead_cost_per_unit=overhead_cost_per_unit,
            total_standard_cost_per_unit=total_standard_cost_per_unit,
            batch_size_used=Decimal(str(self.formula.batch_size)),
            yield_percentage_used=Decimal(str(self.formula.yield_percentage)),
            computed_at=timezone.now(),
            computed_by=self.computed_by,
            currency=overhead_rate.currency,
        )

        self._create_cost_lines(standard_cost, line_costs, total_material_cost_per_batch)
        self._cascade_to_pricing(standard_cost)

        return standard_cost

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _resolve_overhead_rate(self) -> OverheadRate:
        today = timezone.now().date()
        warehouse = self.formula.product.company  # resolved via production order context
        # Overhead rates are warehouse-scoped; the formula itself doesn't carry a
        # warehouse — we look for any rate whose period covers today for the
        # warehouse passed in via the formula's product company warehouses.
        # Callers that know the warehouse should subclass and override this method.
        rate = (
            OverheadRate.objects.filter(
                period_start__lte=today,
                period_end__gte=today,
            )
            .order_by("-period_start")
            .first()
        )
        if rate is None:
            raise NoOverheadRateError(
                "No active OverheadRate found for the current date. "
                "Please create one before approving a formula."
            )
        return rate

    def _material_lines(self):
        return [
            line
            for line in self.formula.lines.all()
            if line.line_type == "MATERIAL" and line.product_id is not None
        ]

    def _compute_line_costs(self, material_lines: list) -> list:
        """
        For each material line resolve a price and compute per-batch cost.
        Returns a list of dicts ready for StandardCostLine creation.
        """
        results = []
        batch_size = Decimal(str(self.formula.batch_size))

        for line in material_lines:
            supplier_product, unit_price = self._resolve_price(line.product)
            quantity_per_batch = Decimal(str(line.quantity))
            quantity_per_unit = quantity_per_batch / batch_size
            cost_per_batch = quantity_per_batch * unit_price

            results.append(
                {
                    "formula_line": line,
                    "product": line.product,
                    "supplier_product": supplier_product,
                    "quantity_per_batch": quantity_per_batch,
                    "quantity_per_unit": quantity_per_unit,
                    "unit_price_used": unit_price,
                    "cost_per_unit": quantity_per_unit * unit_price,
                    "cost_per_batch": cost_per_batch,
                }
            )

        return results

    def _resolve_price(self, product):
        """
        Return (SupplierProduct | None, Decimal price) for an ingredient.

        Priority:
          1. Preferred supplier (is_preferred=True, is_active=True)
          2. Cheapest active supplier
          3. Raise NoPricedIngredientError
        """
        qs = SupplierProduct.objects.filter(product=product, is_active=True)

        preferred = qs.filter(is_preferred=True).first()
        if preferred:
            return preferred, preferred.price

        cheapest = qs.order_by("price").first()
        if cheapest:
            return cheapest, cheapest.price

        raise NoPricedIngredientError(
            f"No supplier price found for ingredient '{product.name}' (id={product.id}). "
            "Add a SupplierProduct record before approving this formula."
        )

    def _create_cost_lines(
        self,
        standard_cost: StandardCost,
        line_costs: list,
        total_material_cost_per_batch: Decimal,
    ):
        lines = []
        for lc in line_costs:
            if total_material_cost_per_batch > 0:
                cost_percentage = (lc["cost_per_batch"] / total_material_cost_per_batch) * Decimal("100")
            else:
                cost_percentage = Decimal("0")

            lines.append(
                StandardCostLine(
                    standard_cost=standard_cost,
                    product=lc["product"],
                    formula_line=lc["formula_line"],
                    quantity_per_batch=lc["quantity_per_batch"],
                    quantity_per_unit=lc["quantity_per_unit"],
                    unit_price_used=lc["unit_price_used"],
                    supplier_product_used=lc["supplier_product"],
                    cost_per_unit=lc["cost_per_unit"],
                    cost_percentage=cost_percentage,
                )
            )

        StandardCostLine.objects.bulk_create(lines)

    def _cascade_to_pricing(self, standard_cost: StandardCost):
        from apps.costing.services.product_pricing_rule_updater import ProductPricingRuleUpdater

        updater = ProductPricingRuleUpdater(standard_cost=standard_cost)
        updater.run()


class WarehouseStandardCostEngine(StandardCostEngine):
    """
    Variant that accepts an explicit warehouse so the overhead rate lookup
    is scoped correctly. Use this from production-order-aware callers.
    """

    def __init__(self, formula, computed_by, warehouse):
        super().__init__(formula, computed_by)
        self.warehouse = warehouse

    def _resolve_overhead_rate(self) -> OverheadRate:
        today = timezone.now().date()
        rate = (
            OverheadRate.objects.filter(
                warehouse=self.warehouse,
                period_start__lte=today,
                period_end__gte=today,
            )
            .order_by("-period_start")
            .first()
        )
        if rate is None:
            raise NoOverheadRateError(
                f"No active OverheadRate found for warehouse '{self.warehouse.name}' "
                f"on {today}. Create one before approving this formula."
            )
        return rate
