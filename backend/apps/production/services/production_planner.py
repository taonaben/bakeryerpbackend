from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum

from apps.formulation.models import Formula, FormulaLine
from apps.inventory.models import Batch


class ProductionPlanner:
    @staticmethod
    def plan(order):
        formula = ProductionPlanner.select_formula(order)
        validate = ProductionPlanner.validate_order(order, formula)
        scale_factor = ProductionPlanner.compute_scale_factor(order, formula)
        shortages = ProductionPlanner.validate_material_availability(
            order, formula, scale_factor
        )
        can_run = not validate and not shortages

        return {
            "formula": formula,
            "scale_factor": scale_factor,
            "shortages": shortages,
            "validation_errors": validate,
            "can_run": can_run,
        }

    @staticmethod
    def select_formula(order):
        if getattr(order, "formula_id", None):
            return order.formula

        formula = (
            Formula.objects.filter(product=order.product, status="active")
            .order_by("-revision", "-created_at")
            .first()
        )
        if not formula:
            raise ValidationError("No active formula found for this product.")

        return formula

    @staticmethod
    def validate_order(order, formula):
        errors = []

        if order.status != "scheduled":
            errors.append("Production order must be scheduled before planning.")

        if order.quantity is None or order.quantity <= 0:
            errors.append("Production order quantity must be greater than 0.")

        if order.warehouse and order.warehouse.wh_type != "production":
            errors.append("Production order warehouse must be a production warehouse.")

        if formula.status != "active":
            errors.append("Formula must be active before starting production.")

        if formula.product_id != order.product_id:
            errors.append("Formula product does not match production order product.")

        if formula.batch_size is None or formula.batch_size <= 0:
            errors.append("Formula batch size must be greater than 0.")

        if errors:
            return errors

    @staticmethod
    def compute_scale_factor(order, formula):
        return Decimal(str(order.quantity)) / Decimal(str(formula.batch_size))

    @staticmethod
    def validate_material_availability(order, formula, scale_factor):
        material_lines = FormulaLine.objects.filter(
            formula=formula, line_type="MATERIAL"
        )

        shortages = {}
        for line in material_lines:
            if not line.product_id:
                continue

            required_qty = Decimal(str(line.quantity or 0)) * scale_factor
            available_qty = (
                Batch.objects.filter(
                    product=line.product, warehouse=order.warehouse, quantity__gt=0
                ).aggregate(total=Sum("quantity"))
            )["total"] or Decimal("0")

            if available_qty < required_qty:
                shortages[line.product.name] = {
                    "available": available_qty,
                    "required": required_qty,
                }

        if shortages:
            return shortages

        return None
