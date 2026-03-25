from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import Batch, StockMovement, StockMovementBatch

from ..models import (
    ProductionOrder,
    ProductionBatch,
    BatchOutput,
    BatchWaste,
)


class ProductionBatchService:
    @staticmethod
    def finish_order(order_id, outputs, waste=None):
        waste = waste or []

        with transaction.atomic():
            order = (
                ProductionOrder.objects.select_for_update()
                .select_related("product", "warehouse")
                .get(id=order_id)
            )

            if order.status != "in_progress":
                raise ValidationError("Production order must be in progress to finish.")

            expected_output, expected_waste = (
                ProductionBatchService._compute_expectations(order)
            )

            batch = (
                ProductionBatch.objects.select_for_update()
                .filter(production_order=order, status="in_progress")
                .order_by("started_at")
                .first()
            )
            if not batch:
                raise ValidationError("No in-progress batch found for this order.")

            if not outputs:
                raise ValidationError("At least one output line is required.")

            total_output_qty = Decimal("0")
            for line in outputs:
                qty = Decimal(str(line["quantity"]))
                if qty <= 0:
                    raise ValidationError("Output quantity must be greater than 0.")
                total_output_qty += qty

            for line in waste:
                qty = Decimal(str(line["quantity"]))
                if qty <= 0:
                    raise ValidationError("Waste quantity must be greater than 0.")

            movement = StockMovement.objects.create(
                warehouse=order.warehouse,
                movement_type="IN",
                total_quantity=total_output_qty,
                reference_number=f"PROD-{batch.batch_number}",
                notes=f"Finished goods for batch {batch.batch_number}",
            )

            output_records = []
            inventory_batches = []
            for line in outputs:
                product = line["product"]
                qty = Decimal(str(line["quantity"]))

                manufacture_date = timezone.now().date()
                expiry_date = manufacture_date + timezone.timedelta(
                    days=product.shelf_life_days or 365
                )

                output_records.append(
                    BatchOutput(
                        production_batch=batch,
                        product=product,
                        quantity_produced=float(qty),
                    )
                )

                inventory_batch = Batch.objects.create(
                    product=product,
                    warehouse=order.warehouse,
                    quantity=Decimal("0"),
                    manufacture_date=manufacture_date,
                    expiry_date=expiry_date,
                )
                StockMovementBatch.objects.create(
                    stock_movement=movement,
                    batch=inventory_batch,
                    quantity=qty,
                )
                inventory_batches.append(inventory_batch)

            BatchOutput.objects.bulk_create(output_records)

            waste_records = []
            for line in waste:
                waste_records.append(
                    BatchWaste(
                        production_batch=batch,
                        product=line["product"],
                        quantity_wasted=float(Decimal(str(line["quantity"]))),
                        reason=line.get("reason"),
                    )
                )
            if waste_records:
                BatchWaste.objects.bulk_create(waste_records)

            main_output_qty = sum(
                Decimal(str(line["quantity"]))
                for line in outputs
                if line["product"].id == order.product_id
            )
            if main_output_qty:
                batch.quantity_produced = float(main_output_qty)
            batch.status = "completed"
            batch.completed_at = timezone.now()
            batch.save(update_fields=["quantity_produced", "status", "completed_at"])

            has_open_batches = (
                ProductionBatch.objects.filter(production_order=order)
                .exclude(status="completed")
                .exists()
            )
            if not has_open_batches:
                order.status = "completed"
                order.save(update_fields=["status"])

            variance = expected_output - main_output_qty

        return {
            "order": order,
            "batch": batch,
            "outputs": output_records,
            "waste": waste_records,
            "movement": movement,
            "inventory_batches": inventory_batches,
            "expected_output": expected_output,
            "expected_waste": expected_waste,
            "actual_output": main_output_qty,
            "variance": variance,
        }

    @staticmethod
    def _compute_expectations(order):
        expected_output = Decimal(str(order.quantity or 0))
        yield_pct = Decimal(str(order.formula.yield_percentage or 0))
        expected_waste = expected_output * (Decimal("100") - yield_pct) / Decimal("100")
        return expected_output, expected_waste
