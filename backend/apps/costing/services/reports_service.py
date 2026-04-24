"""
CostingReportsService
=====================
Query-only aggregations that power the analytics endpoints.
No writes — pure read logic kept separate from the engine services.
"""

from decimal import Decimal
from django.db.models import Avg, F, Max, Min, OuterRef, Subquery


class CostingReportsService:

    @staticmethod
    def cost_trend(product_id, warehouse_id=None, limit=20):
        """
        Cost per unit over time for a product, derived from CostingEntry records.
        Returns a list of dicts ordered by computed_at ascending.
        """
        from apps.costing.models import CostingEntry

        qs = CostingEntry.objects.filter(product_id=product_id).select_related(
            "production_batch", "warehouse"
        )
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)

        qs = qs.order_by("computed_at")[:limit]

        return [
            {
                "costing_entry_id": str(entry.id),
                "batch_number": entry.production_batch.batch_number,
                "warehouse": entry.warehouse.name,
                "cost_per_unit": entry.cost_per_unit,
                "total_cost": entry.total_cost,
                "actual_output_quantity": entry.actual_output_quantity,
                "computed_at": entry.computed_at,
                "currency": entry.currency,
            }
            for entry in qs
        ]

    @staticmethod
    def variance_analysis(product_id=None, warehouse_id=None, date_from=None, date_to=None):
        """
        Variance breakdown aggregated per product, showing average and total variances.
        """
        from django.db.models import Sum, Count, Q
        from apps.costing.models import CostVarianceRecord

        qs = CostVarianceRecord.objects.all()
        if product_id:
            qs = qs.filter(product_id=product_id)
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if date_from:
            qs = qs.filter(computed_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(computed_at__date__lte=date_to)

        rows = (
            qs.values("product_id", "product__name", "warehouse_id", "warehouse__name")
            .annotate(
                total_mpv=Sum("material_price_variance"),
                total_muv=Sum("material_usage_variance"),
                total_yv=Sum("yield_variance"),
                total_ov=Sum("overhead_variance"),
                total_variance=Sum("total_variance"),
                avg_variance_pct=Avg("variance_percentage"),
                batch_count=Count("id"),
                adverse_count=Count("id", filter=Q(is_favourable=False)),
            )
            .order_by("total_variance")
        )

        return list(rows)

    @staticmethod
    def margin_report(product_id=None):
        """
        Gross margin per product using latest CostingEntry cost + ProductPricingRule.
        """
        from apps.costing.models import CostingEntry, ProductPricingRule

        rules = ProductPricingRule.objects.select_related(
            "product", "standard_cost_reference"
        )
        if product_id:
            rules = rules.filter(product_id=product_id)

        results = []
        for rule in rules:
            # Latest actual cost
            latest_entry = (
                CostingEntry.objects.filter(product=rule.product)
                .order_by("-computed_at")
                .first()
            )
            actual_cost = latest_entry.cost_per_unit if latest_entry else None
            std_cost = (
                rule.standard_cost_reference.total_standard_cost_per_unit
                if rule.standard_cost_reference
                else None
            )
            cost_basis = actual_cost or std_cost

            if cost_basis and rule.recommended_selling_price:
                gross_margin_pct = (
                    (rule.recommended_selling_price - cost_basis)
                    / rule.recommended_selling_price
                    * Decimal("100")
                )
            else:
                gross_margin_pct = None

            results.append(
                {
                    "product_id": str(rule.product_id),
                    "product_name": rule.product.name,
                    "actual_cost_per_unit": actual_cost,
                    "standard_cost_per_unit": std_cost,
                    "recommended_selling_price": rule.recommended_selling_price,
                    "minimum_selling_price": rule.minimum_selling_price,
                    "target_gross_margin_percentage": rule.target_gross_margin_percentage,
                    "computed_gross_margin_percentage": gross_margin_pct,
                    "currency": rule.currency,
                }
            )

        return results

    @staticmethod
    def ingredient_cost_breakdown(product_id=None, formula_id=None):
        """
        Which ingredients drive the most cost, ranked by cost_percentage.
        Based on the latest StandardCostLine records.
        """
        from apps.costing.models import StandardCost, StandardCostLine

        if formula_id:
            sc = StandardCost.objects.filter(formula_id=formula_id).order_by("-computed_at").first()
        elif product_id:
            sc = StandardCost.objects.filter(product_id=product_id).order_by("-computed_at").first()
        else:
            return []

        if sc is None:
            return []

        lines = (
            StandardCostLine.objects.filter(standard_cost=sc)
            .select_related("product", "supplier_product_used__supplier")
            .order_by("-cost_percentage")
        )

        return [
            {
                "ingredient_id": str(line.product_id),
                "ingredient_name": line.product.name,
                "quantity_per_unit": line.quantity_per_unit,
                "unit_price_used": line.unit_price_used,
                "cost_per_unit": line.cost_per_unit,
                "cost_percentage": line.cost_percentage,
                "supplier": (
                    line.supplier_product_used.supplier.name
                    if line.supplier_product_used
                    else "Manual override"
                ),
            }
            for line in lines
        ]
