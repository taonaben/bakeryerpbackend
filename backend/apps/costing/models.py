import uuid
from django.db import models
from django.conf import settings
from central.models import Product, Warehouse
from apps.formulation.models import Formula, FormulaLine
from apps.production.models import ProductionBatch, BatchMaterial
from apps.purchasing.models import SupplierProduct


class OverheadRate(models.Model):
    """
    Management-defined record of indirect costs (electricity, rent, labour,
    depreciation) for a given period and facility. Dividing total budgeted
    overhead by planned production units yields the rate absorbed per unit.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="overhead_rates",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    total_overhead_budgeted = models.DecimalField(max_digits=14, decimal_places=2)
    planned_production_units = models.DecimalField(max_digits=14, decimal_places=4)
    # Stored computed field: total_overhead_budgeted / planned_production_units
    rate_per_unit = models.DecimalField(max_digits=14, decimal_places=6)
    planned_labor_minutes = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=(
            "Total planned facility labor driver capacity for this warehouse "
            "and period, not per-product labor usage."
        ),
    )
    rate_per_labor_minute = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=10)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="overhead_rates_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Overhead Rate"
        verbose_name_plural = "Overhead Rates"
        indexes = [
            models.Index(fields=["warehouse", "period_start", "period_end"], name="overhead_wh_period_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.planned_production_units and self.planned_production_units != 0:
            self.rate_per_unit = self.total_overhead_budgeted / self.planned_production_units
        if self.planned_labor_minutes and self.planned_labor_minutes != 0:
            self.rate_per_labor_minute = self.total_overhead_budgeted / self.planned_labor_minutes
        else:
            self.rate_per_labor_minute = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Overhead Rate — {self.warehouse.name} ({self.period_start} to {self.period_end})"


class StandardCost(models.Model):
    """
    Theoretical cost of producing one unit of a product, frozen at the moment
    a formula revision is approved. Serves as the benchmark for variance analysis.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    formula = models.ForeignKey(
        Formula,
        on_delete=models.PROTECT,
        related_name="standard_costs",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="standard_costs",
    )
    overhead_rate = models.ForeignKey(
        OverheadRate,
        on_delete=models.PROTECT,
        related_name="standard_costs",
    )
    material_cost_per_unit = models.DecimalField(max_digits=14, decimal_places=6)
    overhead_cost_per_unit = models.DecimalField(max_digits=14, decimal_places=6)
    overhead_allocation_method = models.CharField(
        max_length=30,
        choices=[
            ("labor_minutes", "Labor Minutes"),
            ("unit_rate", "Unit Rate"),
        ],
        default="unit_rate",
    )
    total_standard_cost_per_unit = models.DecimalField(max_digits=14, decimal_places=6)
    # Snapshot of formula state at computation time
    batch_size_used = models.DecimalField(max_digits=14, decimal_places=4)
    yield_percentage_used = models.DecimalField(max_digits=7, decimal_places=4)
    computed_at = models.DateTimeField()
    computed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="standard_costs_computed",
    )
    currency = models.CharField(max_length=10)

    class Meta:
        verbose_name = "Standard Cost"
        verbose_name_plural = "Standard Costs"
        indexes = [
            models.Index(fields=["product", "computed_at"], name="stdcost_product_date_idx"),
            models.Index(fields=["formula"], name="stdcost_formula_idx"),
        ]

    def __str__(self):
        return f"Standard Cost — {self.product.name} (formula rev {self.formula.revision}, computed {self.computed_at:%Y-%m-%d})"


class StandardCostLine(models.Model):
    """
    Line-by-line material breakdown of a StandardCost. One record per
    ingredient in the formula, enabling ingredient-level cost attribution.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    standard_cost = models.ForeignKey(
        StandardCost,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="standard_cost_lines",
    )
    formula_line = models.ForeignKey(
        FormulaLine,
        on_delete=models.PROTECT,
        related_name="standard_cost_lines",
    )
    quantity_per_batch = models.DecimalField(max_digits=14, decimal_places=6)
    quantity_per_unit = models.DecimalField(max_digits=14, decimal_places=6)
    # Snapshot of supplier price at computation time
    unit_price_used = models.DecimalField(max_digits=14, decimal_places=6)
    supplier_product_used = models.ForeignKey(
        SupplierProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="standard_cost_lines",
    )
    cost_per_unit = models.DecimalField(max_digits=14, decimal_places=6)
    # Percentage of total material cost; computed and stored
    cost_percentage = models.DecimalField(max_digits=7, decimal_places=4)

    class Meta:
        verbose_name = "Standard Cost Line"
        verbose_name_plural = "Standard Cost Lines"
        ordering = ["-cost_percentage"]

    def __str__(self):
        return f"{self.product.name} — {self.cost_percentage}% of material cost"


class CostingEntry(models.Model):
    """
    Actual cost record for a completed production batch. Computed when a
    ProductionBatch is closed. The real counterpart to StandardCost.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_batch = models.OneToOneField(
        ProductionBatch,
        on_delete=models.PROTECT,
        related_name="costing_entry",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="costing_entries",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="costing_entries",
    )
    standard_cost = models.ForeignKey(
        StandardCost,
        on_delete=models.PROTECT,
        related_name="costing_entries",
    )
    overhead_rate = models.ForeignKey(
        OverheadRate,
        on_delete=models.PROTECT,
        related_name="costing_entries",
    )
    total_material_cost = models.DecimalField(max_digits=14, decimal_places=2)
    overhead_cost = models.DecimalField(max_digits=14, decimal_places=2)
    overhead_allocation_method = models.CharField(
        max_length=30,
        choices=[
            ("labor_minutes", "Labor Minutes"),
            ("unit_rate", "Unit Rate"),
        ],
        default="unit_rate",
    )
    total_cost = models.DecimalField(max_digits=14, decimal_places=2)
    actual_output_quantity = models.DecimalField(max_digits=14, decimal_places=4)
    actual_waste_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    cost_per_unit = models.DecimalField(max_digits=14, decimal_places=6)
    computed_at = models.DateTimeField()
    currency = models.CharField(max_length=10)

    class Meta:
        verbose_name = "Costing Entry"
        verbose_name_plural = "Costing Entries"
        indexes = [
            models.Index(fields=["product", "computed_at"], name="costentry_product_date_idx"),
            models.Index(fields=["warehouse", "computed_at"], name="costentry_wh_date_idx"),
        ]

    def __str__(self):
        return f"Costing Entry — {self.product.name} batch {self.production_batch.batch_number}"


class CostingEntryLine(models.Model):
    """
    Line-by-line actual material breakdown of a CostingEntry. Mirrors
    StandardCostLine but uses actual quantities and prices from the batch.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    costing_entry = models.ForeignKey(
        CostingEntry,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="costing_entry_lines",
    )
    batch_material = models.ForeignKey(
        BatchMaterial,
        on_delete=models.PROTECT,
        related_name="costing_entry_lines",
    )
    actual_quantity_used = models.DecimalField(max_digits=14, decimal_places=6)
    unit_price_used = models.DecimalField(max_digits=14, decimal_places=6)
    actual_cost = models.DecimalField(max_digits=14, decimal_places=6)

    class Meta:
        verbose_name = "Costing Entry Line"
        verbose_name_plural = "Costing Entry Lines"

    def __str__(self):
        return f"{self.product.name} — actual cost {self.actual_cost}"


class CostVarianceRecord(models.Model):
    """
    Comparison between StandardCost and CostingEntry for a batch.
    Produces four named variances: price, usage, yield, and overhead.
    Computed automatically when a CostingEntry is created.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    costing_entry = models.OneToOneField(
        CostingEntry,
        on_delete=models.CASCADE,
        related_name="variance_record",
    )
    standard_cost = models.ForeignKey(
        StandardCost,
        on_delete=models.PROTECT,
        related_name="variance_records",
    )
    production_batch = models.ForeignKey(
        ProductionBatch,
        on_delete=models.PROTECT,
        related_name="variance_records",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="variance_records",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="variance_records",
    )

    # Σ (standard_price - actual_price) × actual_quantity_used
    # Positive = favourable (paid less than expected)
    material_price_variance = models.DecimalField(max_digits=14, decimal_places=4)

    # Σ (standard_quantity - actual_quantity) × standard_price
    # Positive = favourable (used less material)
    material_usage_variance = models.DecimalField(max_digits=14, decimal_places=4)

    # (actual_output - standard_output) × standard_cost_per_unit
    # Positive = favourable (produced more than expected)
    yield_variance = models.DecimalField(max_digits=14, decimal_places=4)

    # (standard_overhead_per_unit - actual_overhead_per_unit) × actual_output
    # Positive = favourable
    overhead_variance = models.DecimalField(max_digits=14, decimal_places=4)

    total_variance = models.DecimalField(max_digits=14, decimal_places=4)
    variance_percentage = models.DecimalField(max_digits=9, decimal_places=4)
    is_favourable = models.BooleanField()
    computed_at = models.DateTimeField()

    class Meta:
        verbose_name = "Cost Variance Record"
        verbose_name_plural = "Cost Variance Records"
        indexes = [
            models.Index(fields=["product", "computed_at"], name="variance_product_date_idx"),
            models.Index(fields=["warehouse", "is_favourable"], name="variance_wh_favourable_idx"),
        ]

    def __str__(self):
        direction = "FAV" if self.is_favourable else "ADV"
        return f"Variance [{direction}] — {self.product.name} batch {self.production_batch.batch_number}"


class ProductPricingRule(models.Model):
    """
    Management-defined pricing parameters for a finished product. Sets the
    target margin and computes minimum and recommended selling prices based
    on the latest StandardCost. Creates a hard floor to prevent below-cost sales.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.OneToOneField(
        Product,
        on_delete=models.PROTECT,
        related_name="pricing_rule",
    )
    target_gross_margin_percentage = models.DecimalField(max_digits=7, decimal_places=4)
    minimum_margin_percentage = models.DecimalField(max_digits=7, decimal_places=4)
    standard_cost_reference = models.ForeignKey(
        StandardCost,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pricing_rules",
    )
    # Computed: standard_cost / (1 - target_margin / 100)
    recommended_selling_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    # Computed: standard_cost / (1 - minimum_margin / 100) — hard floor
    minimum_selling_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=10)
    last_updated = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pricing_rules_updated",
    )

    class Meta:
        verbose_name = "Product Pricing Rule"
        verbose_name_plural = "Product Pricing Rules"

    def __str__(self):
        return f"Pricing Rule — {self.product.name} (target margin {self.target_gross_margin_percentage}%)"
