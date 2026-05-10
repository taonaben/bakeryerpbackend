"""
CostingEngine
=============
Triggered when a ProductionBatch.status transitions to "completed".

Responsibilities:
  1. Resolve the StandardCost for the batch's formula.
  2. Resolve the OverheadRate active on the batch's completion date.
  3. Price each BatchMaterial line at the price valid on the batch's start date.
  4. Compute actual material cost, overhead cost, totals, and cost per unit.
  5. Persist CostingEntry + CostingEntryLine records (one-to-one with batch).
  6. Immediately trigger VarianceEngine.
"""

import logging
from decimal import Decimal
from django.db import transaction

from apps.costing.models import (
    CostingEntry,
    CostingEntryLine,
    OverheadRate,
    StandardCost,
)
from apps.production.models import BatchMaterial, BatchOutput, BatchWaste
from apps.purchasing.models import SupplierProduct

logger = logging.getLogger(__name__)


class CostingEngineError(Exception):
    """Fatal error that prevents CostingEntry creation."""


class CostingEngine:
    """
    Compute and persist a CostingEntry for a completed ProductionBatch.

    Usage::

        engine = CostingEngine(production_batch=batch)
        costing_entry = engine.run()
    """

    def __init__(self, production_batch):
        self.batch = production_batch

    # ------------------------------------------------------------------ #
    #  Public entry point                                                  #
    # ------------------------------------------------------------------ #

    @transaction.atomic
    def run(self) -> CostingEntry:
        # Guard: one CostingEntry per batch
        if hasattr(self.batch, "costing_entry"):
            return self.batch.costing_entry

        actual_output = self._actual_output()
        if actual_output == 0:
            raise CostingEngineError(
                f"Batch {self.batch.batch_number} has zero actual output. "
                "Cannot create a CostingEntry for a zero-output batch."
            )

        standard_cost = self._resolve_standard_cost()
        overhead_rate = self._resolve_overhead_rate()
        line_costs, requires_review = self._compute_line_costs()

        total_material_cost = sum(lc["actual_cost"] for lc in line_costs)
        overhead_cost, overhead_allocation_method = self._compute_overhead_cost(
            overhead_rate,
            actual_output,
        )
        total_cost = total_material_cost + overhead_cost
        cost_per_unit = total_cost / actual_output
        actual_waste = self._actual_waste()

        warehouse = self.batch.production_order.warehouse

        costing_entry = CostingEntry.objects.create(
            production_batch=self.batch,
            product=self.batch.production_order.product,
            warehouse=warehouse,
            standard_cost=standard_cost,
            overhead_rate=overhead_rate,
            total_material_cost=total_material_cost.quantize(Decimal("0.01")),
            overhead_cost=overhead_cost.quantize(Decimal("0.01")),
            overhead_allocation_method=overhead_allocation_method,
            total_cost=total_cost.quantize(Decimal("0.01")),
            actual_output_quantity=actual_output,
            actual_waste_quantity=actual_waste,
            cost_per_unit=cost_per_unit,
            computed_at=self.batch.completed_at,
            currency=standard_cost.currency,
        )

        self._create_entry_lines(costing_entry, line_costs)

        if requires_review:
            logger.warning(
                "CostingEntry %s for batch %s has unpriced ingredients and requires review.",
                costing_entry.id,
                self.batch.batch_number,
            )

        self._trigger_variance_engine(costing_entry)

        return costing_entry

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _resolve_standard_cost(self) -> StandardCost:
        formula = self.batch.production_order.formula
        sc = StandardCost.objects.filter(formula=formula).order_by("-computed_at").first()
        if sc is None:
            raise CostingEngineError(
                f"No StandardCost found for formula '{formula}' "
                f"(revision {formula.revision}). Approve the formula first."
            )
        return sc

    def _resolve_overhead_rate(self) -> OverheadRate:
        # Use the batch's completion date, not today — historical accuracy
        reference_date = (
            self.batch.completed_at.date()
            if self.batch.completed_at
            else self.batch.started_at.date()
        )
        warehouse = self.batch.production_order.warehouse
        rate = (
            OverheadRate.objects.filter(
                warehouse=warehouse,
                period_start__lte=reference_date,
                period_end__gte=reference_date,
            )
            .order_by("-period_start")
            .first()
        )
        if rate is None:
            raise CostingEngineError(
                f"No OverheadRate found for warehouse '{warehouse.name}' "
                f"on {reference_date}. Cannot cost batch {self.batch.batch_number}."
            )
        return rate

    def _compute_overhead_cost(self, overhead_rate, actual_output):
        formula = self.batch.production_order.formula
        labor_minutes = formula.labor_minutes_per_batch
        labor_rate = overhead_rate.rate_per_labor_minute

        if labor_minutes is not None and labor_rate is not None:
            effective_units = Decimal(str(formula.batch_size)) * (
                Decimal(str(formula.yield_percentage)) / Decimal("100")
            )
            if effective_units <= 0:
                raise CostingEngineError(
                    "Formula effective units must be greater than zero for costing."
                )

            labor_minutes_per_unit = Decimal(str(labor_minutes)) / effective_units
            return (
                actual_output * labor_minutes_per_unit * labor_rate,
                "labor_minutes",
            )

        return actual_output * overhead_rate.rate_per_unit, "unit_rate"

    def _compute_line_costs(self):
        """
        Price each BatchMaterial at the rate valid on the batch's start date.
        Returns (list_of_line_cost_dicts, requires_review_flag).
        """
        results = []
        requires_review = False
        batch_start = self.batch.started_at.date()

        for bm in BatchMaterial.objects.filter(production_batch=self.batch):
            price, found = self._price_at_date(bm.product, batch_start)
            if not found:
                requires_review = True
                logger.warning(
                    "No supplier price found for ingredient '%s' on %s. "
                    "Using price=0 and flagging for review.",
                    bm.product.name,
                    batch_start,
                )

            qty = Decimal(str(bm.quantity_used))
            results.append(
                {
                    "batch_material": bm,
                    "product": bm.product,
                    "actual_quantity_used": qty,
                    "unit_price_used": price,
                    "actual_cost": qty * price,
                }
            )

        return results, requires_review

    def _price_at_date(self, product, date):
        """
        Return (price: Decimal, found: bool) for a product on a given date.

        Priority:
          1. Preferred active SupplierProduct
          2. Cheapest active SupplierProduct
          3. (0, False) — flags the entry for review
        """
        qs = SupplierProduct.objects.filter(product=product, is_active=True)

        preferred = qs.filter(is_preferred=True).first()
        if preferred:
            return preferred.price, True

        cheapest = qs.order_by("price").first()
        if cheapest:
            return cheapest.price, True

        return Decimal("0"), False

    def _actual_output(self) -> Decimal:
        total = Decimal("0")
        for output in BatchOutput.objects.filter(
            production_batch=self.batch,
            product=self.batch.production_order.product,
        ):
            total += Decimal(str(output.quantity_produced))
        return total

    def _actual_waste(self) -> Decimal:
        total = Decimal("0")
        for waste in BatchWaste.objects.filter(production_batch=self.batch):
            total += Decimal(str(waste.quantity_wasted))
        return total

    def _create_entry_lines(self, costing_entry: CostingEntry, line_costs: list):
        lines = [
            CostingEntryLine(
                costing_entry=costing_entry,
                product=lc["product"],
                batch_material=lc["batch_material"],
                actual_quantity_used=lc["actual_quantity_used"],
                unit_price_used=lc["unit_price_used"],
                actual_cost=lc["actual_cost"],
            )
            for lc in line_costs
        ]
        CostingEntryLine.objects.bulk_create(lines)

    def _trigger_variance_engine(self, costing_entry: CostingEntry):
        from apps.costing.services.variance_engine import VarianceEngine

        try:
            engine = VarianceEngine(costing_entry=costing_entry)
            engine.run()
        except Exception as exc:
            # VarianceEngine must never block CostingEntry persistence
            logger.error(
                "VarianceEngine failed for CostingEntry %s: %s. "
                "The CostingEntry has been saved; variance record is pending.",
                costing_entry.id,
                exc,
                exc_info=True,
            )
