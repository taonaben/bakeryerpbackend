from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import Batch, StockMovement, StockMovementBatch

from ..models import ReworkOrder, ReworkInput, ReworkOutput


class ReworkService:
    @staticmethod
    def start_rework(order_id, inputs):
        if not inputs:
            raise ValidationError("At least one input batch is required.")

        with transaction.atomic():
            order = (
                ReworkOrder.objects.select_for_update()
                .select_related("warehouse", "target_product")
                .get(id=order_id)
            )

            if order.status != "scheduled":
                raise ValidationError("Rework order must be scheduled to start.")

            total_input = Decimal("0")
            input_records = []
            movement = StockMovement.objects.create(
                warehouse=order.warehouse,
                movement_type="OUT",
                total_quantity=Decimal("0"),
                reference_number=f"REWORK-{order.id}",
                notes="Rework input consumption",
            )

            for line in inputs:
                batch_id = line.get("batch_id")
                qty = Decimal(str(line.get("quantity")))
                if qty <= 0:
                    raise ValidationError("Input quantity must be greater than 0.")

                stock_batch = Batch.objects.select_for_update().get(id=batch_id)
                if stock_batch.warehouse_id != order.warehouse_id:
                    raise ValidationError("Input batch warehouse does not match order.")
                if Decimal(str(stock_batch.quantity)) < qty:
                    raise ValidationError("Input batch does not have enough quantity.")

                StockMovementBatch.objects.create(
                    stock_movement=movement,
                    batch=stock_batch,
                    quantity=qty,
                )

                input_records.append(
                    ReworkInput(
                        rework_order=order,
                        batch=stock_batch,
                        quantity_used=float(qty),
                        notes=line.get("notes"),
                    )
                )
                total_input += qty

            movement.total_quantity = total_input
            movement.save(update_fields=["total_quantity"])

            ReworkInput.objects.bulk_create(input_records)

            order.status = "in_progress"
            order.save(update_fields=["status"])

        return {
            "order": order,
            "movement": movement,
            "inputs": input_records,
            "total_input": total_input,
        }

    @staticmethod
    def finish_rework(order_id, outputs):
        if not outputs:
            raise ValidationError("At least one output line is required.")

        with transaction.atomic():
            order = (
                ReworkOrder.objects.select_for_update()
                .select_related("warehouse", "target_product")
                .get(id=order_id)
            )

            if order.status != "in_progress":
                raise ValidationError("Rework order must be in progress to finish.")

            total_output = Decimal("0")
            for line in outputs:
                qty = Decimal(str(line.get("quantity")))
                if qty <= 0:
                    raise ValidationError("Output quantity must be greater than 0.")
                if line.get("product").id != order.target_product_id:
                    raise ValidationError("Output product must match target product.")
                total_output += qty

            if order.quantity_requested and total_output > Decimal(
                str(order.quantity_requested)
            ):
                raise ValidationError(
                    "Output quantity cannot exceed requested quantity."
                )

            movement = StockMovement.objects.create(
                warehouse=order.warehouse,
                movement_type="IN",
                total_quantity=total_output,
                reference_number=f"REWORK-{order.id}",
                notes="Rework output production",
            )

            output_records = []
            inventory_batches = []
            for line in outputs:
                product = line.get("product")
                qty = Decimal(str(line.get("quantity")))

                manufacture_date = timezone.now().date()
                expiry_date = manufacture_date + timezone.timedelta(
                    days=product.shelf_life_days or 365
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

                output_records.append(
                    ReworkOutput(
                        rework_order=order,
                        product=product,
                        quantity_produced=float(qty),
                        output_batch=inventory_batch,
                    )
                )
                inventory_batches.append(inventory_batch)

            ReworkOutput.objects.bulk_create(output_records)

            order.status = "completed"
            order.completed_at = timezone.now()
            order.save(update_fields=["status", "completed_at"])

        return {
            "order": order,
            "movement": movement,
            "outputs": output_records,
            "inventory_batches": inventory_batches,
            "total_output": total_output,
        }
