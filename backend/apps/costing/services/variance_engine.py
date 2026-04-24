"""
VarianceEngine
==============
Triggered immediately after CostingEngine creates a CostingEntry.

Produces four named variances:
  - Material Price Variance  (MPV)
  - Material Usage Variance  (MUV)
  - Yield Variance           (YV)
  - Overhead Variance        (OV)

Design rule: this engine must NEVER block. If it fails, the CostingEntry
is already saved and the variance record is left pending for manual resolution.
"""

import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.costing.models import (
    CostingEntry,
    CostingEntryLine,
    CostVarianceRecord,
    StandardCostLine,
)

logger = logging.getLogger(__name__)

# Variance alert threshold — flag for management attention if exceeded
VARIANCE_ALERT_THRESHOLD_PCT = Decimal("10.0")


class VarianceEngine:
    """
    Compute and persist a CostVarianceRecord for a CostingEntry.

    Usage::

        engine = VarianceEngine(costing_entry=costing_entry)
        record = engine.run()
    """

    def __init__(self, costing_entry: CostingEntry):
        self.entry = costing_entry
        self.standard_cost = costing_entry.standard_cost

    # ------------------------------------------------------------------ #
    #  Public entry point                                                  #
    # ------------------------------------------------------------------ #

    @transaction.atomic
    def run(self) -> CostVarianceRecord:
        # Guard: one variance record per costing entry
        if hasattr(self.entry, "variance_record"):
            return self.entry.variance_record

        actual_output = self.entry.actual_output_quantity
        std_cost_per_unit = self.standard_cost.total_standard_cost_per_unit

        mpv = self._material_price_variance()
        muv = self._material_usage_variance(actual_output)
        yv = self._yield_variance(actual_output, std_cost_per_unit)
        ov = self._overhead_variance(actual_output)

        total_variance = mpv + muv + yv + ov

        standard_total_cost = std_cost_per_unit * actual_output
        if standard_total_cost != 0:
            variance_pct = (total_variance / standard_total_cost) * Decimal("100")
        else:
            variance_pct = Decimal("0")

        record = CostVarianceRecord.objects.create(
            costing_entry=self.entry,
            standard_cost=self.standard_cost,
            production_batch=self.entry.production_batch,
            product=self.entry.product,
            warehouse=self.entry.warehouse,
            material_price_variance=mpv,
            material_usage_variance=muv,
            yield_variance=yv,
            overhead_variance=ov,
            total_variance=total_variance,
            variance_percentage=variance_pct,
            is_favourable=total_variance > 0,
            computed_at=timezone.now(),
        )

        self._check_threshold_alert(record)

        return record

    # ------------------------------------------------------------------ #
    #  Variance computations                                               #
    # ------------------------------------------------------------------ #

    def _material_price_variance(self) -> Decimal:
        """
        MPV = Σ (standard_price - actual_price) × actual_quantity_used
        Positive = favourable (paid less than expected).
        """
        mpv = Decimal("0")
        std_lines = {
            scl.product_id: scl
            for scl in StandardCostLine.objects.filter(standard_cost=self.standard_cost)
        }

        for actual_line in CostingEntryLine.objects.filter(costing_entry=self.entry):
            std_line = std_lines.get(actual_line.product_id)
            if std_line is None:
                continue  # ingredient not in standard — skip (new ingredient added mid-run)
            price_diff = std_line.unit_price_used - actual_line.unit_price_used
            mpv += price_diff * actual_line.actual_quantity_used

        return mpv

    def _material_usage_variance(self, actual_output: Decimal) -> Decimal:
        """
        MUV = Σ (standard_quantity_for_actual_output - actual_quantity_used) × standard_price
        Positive = favourable (used less material than expected).
        """
        muv = Decimal("0")
        std_lines = {
            scl.product_id: scl
            for scl in StandardCostLine.objects.filter(standard_cost=self.standard_cost)
        }

        for actual_line in CostingEntryLine.objects.filter(costing_entry=self.entry):
            std_line = std_lines.get(actual_line.product_id)
            if std_line is None:
                continue
            standard_qty_for_output = std_line.quantity_per_unit * actual_output
            qty_diff = standard_qty_for_output - actual_line.actual_quantity_used
            muv += qty_diff * std_line.unit_price_used

        return muv

    def _yield_variance(self, actual_output: Decimal, std_cost_per_unit: Decimal) -> Decimal:
        """
        YV = (actual_output - standard_output_from_actual_input) × standard_cost_per_unit

        standard_output_from_actual_input:
          Derive how many units the formula says we should have gotten from
          the total input we actually fed in.

          standard_input_per_unit = batch_size / effective_units
          standard_output = total_actual_input / standard_input_per_unit
        """
        batch_size = self.standard_cost.batch_size_used
        yield_pct = self.standard_cost.yield_percentage_used
        effective_units = batch_size * (yield_pct / Decimal("100"))

        if effective_units == 0 or batch_size == 0:
            return Decimal("0")

        standard_input_per_unit = batch_size / effective_units

        # Total actual input = sum of all material quantities used
        total_actual_input = sum(
            line.actual_quantity_used
            for line in CostingEntryLine.objects.filter(costing_entry=self.entry)
        )

        if standard_input_per_unit == 0:
            return Decimal("0")

        standard_output_from_actual_input = total_actual_input / standard_input_per_unit
        yield_variance = (actual_output - standard_output_from_actual_input) * std_cost_per_unit

        return yield_variance

    def _overhead_variance(self, actual_output: Decimal) -> Decimal:
        """
        OV = (standard_overhead_per_unit - actual_overhead_per_unit) × actual_output
        Positive = favourable (absorbed more overhead than actually incurred).
        """
        standard_overhead_per_unit = self.standard_cost.overhead_cost_per_unit
        actual_overhead_per_unit = self.entry.overhead_rate.rate_per_unit
        return (standard_overhead_per_unit - actual_overhead_per_unit) * actual_output

    # ------------------------------------------------------------------ #
    #  Threshold alert                                                     #
    # ------------------------------------------------------------------ #

    def _check_threshold_alert(self, record: CostVarianceRecord):
        """
        Log a warning (and optionally create a notification) when the absolute
        variance percentage exceeds the configured threshold.
        """
        if abs(record.variance_percentage) > VARIANCE_ALERT_THRESHOLD_PCT:
            direction = "FAVOURABLE" if record.is_favourable else "ADVERSE"
            logger.warning(
                "VARIANCE ALERT [%s]: Batch %s for product '%s' has a variance of %.4f%% "
                "(threshold: %.1f%%). Total variance: %s. Review required.",
                direction,
                record.production_batch.batch_number,
                record.product.name,
                record.variance_percentage,
                VARIANCE_ALERT_THRESHOLD_PCT,
                record.total_variance,
            )
