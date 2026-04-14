from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.formulation.models import FormulaLine
from apps.inventory.models import Batch, StockMovement, StockMovementBatch
from apps.inventory.services.batch_retrieval import create_stock_movement_with_policy

from ..models import (
    ProductionBatch,
    ProductionBatchLine,
    BatchMaterial,
    ProductionOrder,
)
from .production_planner import ProductionPlanner


class ProductionEngine:
    @staticmethod
    def start_production(order_id, quantity=None, selected_batches=None):
        selected_batches = selected_batches or []

        with transaction.atomic():
            order = (
                ProductionOrder.objects.select_for_update()
                .select_related("product", "warehouse", "formula")
                .get(id=order_id)
            )

            run_qty = (
                Decimal(str(quantity))
                if quantity is not None
                else Decimal(str(order.quantity))
            )
            if run_qty <= 0:
                raise ValidationError("Production quantity must be greater than 0.")
            if run_qty > Decimal(str(order.quantity)):
                raise ValidationError(
                    "Production quantity cannot exceed order quantity."
                )

            formula = ProductionPlanner.select_formula(order)
            scale_factor = run_qty / Decimal(str(formula.batch_size))

            validation_errors = ProductionPlanner.validate_order(order, formula)
            if validation_errors:
                raise ValidationError({"validation_errors": validation_errors})

            shortages = ProductionPlanner.validate_material_availability(
                order, formula, scale_factor
            )
            if shortages:
                raise ValidationError({"shortages": shortages})

            plan = {
                "formula": formula,
                "scale_factor": scale_factor,
                "shortages": shortages,
                "validation_errors": validation_errors,
                "can_run": not validation_errors and not shortages,
            }

            batch = ProductionBatch.objects.create(
                production_order=order,
                batch_number=ProductionEngine._generate_batch_number(),
                quantity_produced=float(run_qty),
                status="in_progress",
            )

            if order.status == "scheduled":
                order.status = "in_progress"
                order.save(update_fields=["status"])
                if order.planned_order_id and order.planned_order.status != "started":
                    order.planned_order.status = "started"
                    order.planned_order.save(update_fields=["status"])

            formula_lines = FormulaLine.objects.filter(formula=formula).order_by(
                "sequence"
            )

            batch_lines = []
            material_lines = []
            for line in formula_lines:
                line_qty = Decimal(str(line.quantity or 0))
                scaled_qty = line_qty * scale_factor
                batch_lines.append(
                    ProductionBatchLine(
                        production_batch=batch,
                        sequence=line.sequence,
                        line_type=line.line_type,
                        product=line.product,
                        quantity=(
                            float(scaled_qty) if line.quantity is not None else 0.0
                        ),
                        text=line.text,
                    )
                )

                if line.line_type == "MATERIAL" and line.product_id:
                    material_lines.append((line.product, scaled_qty))

            ProductionBatchLine.objects.bulk_create(batch_lines)

            movements = []
            selected_map = ProductionEngine._group_selected_batches(selected_batches)
            for product, required_qty in material_lines:
                BatchMaterial.objects.create(
                    production_batch=batch,
                    product=product,
                    quantity_used=float(required_qty),
                )

                allocations = selected_map.get(str(product.id))
                if allocations:
                    movement = ProductionEngine._create_explicit_movement(
                        product=product,
                        warehouse=order.warehouse,
                        allocations=allocations,
                        required_qty=required_qty,
                        batch=batch,
                    )
                else:
                    movement = create_stock_movement_with_policy(
                        product=product,
                        warehouse=order.warehouse,
                        movement_type="OUT",
                        quantity=float(required_qty),
                        reference=f"PROD-{batch.batch_number}",
                        notes=f"Material consumption for batch {batch.batch_number}",
                    )
                    if movement.warehouse_id is None:
                        movement.warehouse = order.warehouse
                        movement.save(update_fields=["warehouse"])

                movements.append(movement)

        return {
            "batch": batch,
            "movements": movements,
            "plan": plan,
        }

    @staticmethod
    def _generate_batch_number():
        return f"PB-{uuid.uuid4().hex[:8].upper()}"

    @staticmethod
    def _group_selected_batches(selected_batches):
        grouped = {}
        for entry in selected_batches:
            product_id = str(entry.get("product_id"))
            grouped.setdefault(product_id, []).append(entry)
        return grouped

    @staticmethod
    def _create_explicit_movement(product, warehouse, allocations, required_qty, batch):
        required_qty = Decimal(str(required_qty))
        total_allocated = Decimal("0")

        movement = StockMovement.objects.create(
            warehouse=warehouse,
            movement_type="OUT",
            total_quantity=required_qty,
            reference_number=f"PROD-{batch.batch_number}",
            notes=f"Material consumption for batch {batch.batch_number}",
        )

        for allocation in allocations:
            batch_id = allocation.get("batch_id")
            qty = Decimal(str(allocation.get("quantity", 0)))
            if qty <= 0:
                raise ValidationError("Selected batch quantity must be greater than 0.")

            stock_batch = Batch.objects.select_for_update().get(id=batch_id)
            if stock_batch.product_id != product.id:
                raise ValidationError("Selected batch product does not match material.")
            if stock_batch.warehouse_id != warehouse.id:
                raise ValidationError("Selected batch warehouse does not match order.")
            if Decimal(str(stock_batch.quantity)) < qty:
                raise ValidationError("Selected batch does not have enough quantity.")

            StockMovementBatch.objects.create(
                stock_movement=movement,
                batch=stock_batch,
                quantity=qty,
            )
            total_allocated += qty

        if total_allocated < required_qty:
            raise ValidationError("Selected batches do not cover required quantity.")
        if total_allocated > required_qty:
            raise ValidationError("Selected batches exceed required quantity.")

        return movement
