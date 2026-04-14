from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from ..models import Batch, Product, StockMovement, StockMovementBatch
from ..utils import recalculate_stock_for_product_warehouse


def create_stock_movement(request_data, serializer_class, context=None):
    movement_data = request_data.copy()
    if "warehouse" not in movement_data and "warehouse_id" in movement_data:
        movement_data["warehouse"] = movement_data.get("warehouse_id")

    warehouse_id = movement_data.get("warehouse")
    if not warehouse_id:
        raise ValidationError({"warehouse": "warehouse field is required."})

    if "total_quantity" not in movement_data and "quantity" in movement_data:
        movement_data["total_quantity"] = movement_data.get("quantity")

    for key in [
        "batch",
        "batch_id",
        "batch_number",
        "product",
        "product_id",
        "manufacture_date",
        "expiry_date",
        "quantity",
        "warehouse_id",
    ]:
        movement_data.pop(key, None)

    serializer = serializer_class(data=movement_data, context=context)
    serializer.is_valid(raise_exception=True)

    return _create_movement_and_batches(serializer, request_data)


def _create_movement_and_batches(serializer, request_data):
    movement_type = serializer.validated_data.get("movement_type")
    total_qty = serializer.validated_data.get("total_quantity")
    if total_qty is None:
        raise ValidationError({"total_quantity": "Quantity is required."})
    if total_qty <= 0:
        raise ValidationError({"total_quantity": "Quantity must be greater than 0."})

    batch_id = request_data.get("batch") or request_data.get("batch_id")
    product_id = request_data.get("product") or request_data.get("product_id")

    with transaction.atomic():
        movement = serializer.save()

        if batch_id:
            try:
                batch = Batch.objects.select_for_update().get(id=batch_id)
            except Batch.DoesNotExist as exc:
                raise ValidationError({"batch": "Batch not found."}) from exc
            if batch.warehouse_id != movement.warehouse_id:
                raise ValidationError(
                    {"batch": "Batch warehouse must match movement warehouse."}
                )
            StockMovementBatch.objects.create(
                stock_movement=movement,
                batch=batch,
                quantity=total_qty,
            )
        elif movement_type == "IN":
            if not product_id:
                raise ValidationError(
                    {"product": "Product is required for IN movements."}
                )
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist as exc:
                raise ValidationError({"product": "Product not found."}) from exc

            manufacture_date_raw = request_data.get("manufacture_date")
            expiry_date_raw = request_data.get("expiry_date")

            manufacture_date = (
                parse_date(manufacture_date_raw)
                if manufacture_date_raw
                else timezone.now().date()
            )
            if manufacture_date_raw and manufacture_date is None:
                raise ValidationError(
                    {"manufacture_date": "Invalid manufacture_date format."}
                )

            expiry_date = parse_date(expiry_date_raw) if expiry_date_raw else None
            if expiry_date_raw and expiry_date is None:
                raise ValidationError({"expiry_date": "Invalid expiry_date format."})

            if expiry_date is None and product.shelf_life_days:
                expiry_date = manufacture_date + timezone.timedelta(
                    days=product.shelf_life_days
                )

            batch_payload = {
                "product": product,
                "warehouse": movement.warehouse,
                "quantity": Decimal("0"),
                "manufacture_date": manufacture_date,
                "expiry_date": expiry_date,
            }
            batch_number = request_data.get("batch_number")
            if batch_number:
                batch_payload["batch_number"] = batch_number

            batch = Batch.objects.create(**batch_payload)

            StockMovementBatch.objects.create(
                stock_movement=movement,
                batch=batch,
                quantity=total_qty,
            )

    return movement


def update_stock_for_batch(batch):
    recalculate_stock_for_product_warehouse(batch.product, batch.warehouse)


def apply_movement_batch(instance):
    batch = instance.batch
    quantity = instance.quantity
    movement_type = instance.stock_movement.movement_type
    reference_number = instance.stock_movement.reference_number or ""

    with transaction.atomic():
        if movement_type == "OUT" or movement_type == "RETURN":
            Batch.objects.filter(id=batch.id).update(quantity=F("quantity") - quantity)
        elif movement_type == "IN":
            Batch.objects.filter(id=batch.id).update(quantity=F("quantity") + quantity)
        elif movement_type == "ADJUSTMENT":
            Batch.objects.filter(id=batch.id).update(quantity=F("quantity") + quantity)

        if movement_type == "OUT" and reference_number.startswith("REWORK-"):
            updated_batch = Batch.objects.get(id=batch.id)
            if updated_batch.quantity <= 0 and not updated_batch.rework_consumed:
                Batch.objects.filter(id=batch.id).update(rework_consumed=True)

        recalculate_stock_for_product_warehouse(batch.product, batch.warehouse)


def reverse_movement_batch(instance):
    batch = instance.batch
    quantity = instance.quantity
    movement_type = instance.stock_movement.movement_type

    with transaction.atomic():
        try:
            if movement_type == "OUT" or movement_type == "RETURN":
                Batch.objects.filter(id=batch.id).update(
                    quantity=F("quantity") + quantity
                )
            elif movement_type == "IN":
                Batch.objects.filter(id=batch.id).update(
                    quantity=F("quantity") - quantity
                )
            elif movement_type == "ADJUSTMENT":
                Batch.objects.filter(id=batch.id).update(
                    quantity=F("quantity") - quantity
                )
        except Batch.DoesNotExist:
            pass

        recalculate_stock_for_product_warehouse(batch.product, batch.warehouse)


def repair_missing_movement_batches(request_data):
    overrides = request_data.get("overrides") or []
    overrides_map = {}
    for override in overrides:
        if not isinstance(override, dict):
            raise ValidationError({"overrides": "Each override must be an object."})
        movement_id = override.get("movement_id")
        if movement_id:
            overrides_map[str(movement_id)] = override

    default_product_id = request_data.get("default_product_id")
    default_batch_number = request_data.get("default_batch_number")
    default_manufacture_date_raw = request_data.get("default_manufacture_date")
    default_expiry_date_raw = request_data.get("default_expiry_date")

    default_manufacture_date = None
    if default_manufacture_date_raw:
        default_manufacture_date = parse_date(default_manufacture_date_raw)
        if default_manufacture_date is None:
            raise ValidationError({"default_manufacture_date": "Invalid date format."})

    default_expiry_date = None
    if default_expiry_date_raw:
        default_expiry_date = parse_date(default_expiry_date_raw)
        if default_expiry_date is None:
            raise ValidationError({"default_expiry_date": "Invalid date format."})

    results = {"created": [], "skipped": []}

    movements = StockMovement.objects.filter(
        stockmovementbatch__isnull=True
    ).select_related("warehouse")

    for movement in movements:
        if movement.movement_type != "IN":
            results["skipped"].append(
                {
                    "movement_id": str(movement.id),
                    "reason": "unsupported_movement_type",
                }
            )
            continue

        if movement.warehouse_id is None:
            results["skipped"].append(
                {"movement_id": str(movement.id), "reason": "missing_warehouse"}
            )
            continue

        override = overrides_map.get(str(movement.id), {})
        product_id = override.get("product_id") or default_product_id
        if not product_id:
            results["skipped"].append(
                {"movement_id": str(movement.id), "reason": "missing_product_id"}
            )
            continue

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            results["skipped"].append(
                {"movement_id": str(movement.id), "reason": "product_not_found"}
            )
            continue

        manufacture_date_raw = override.get("manufacture_date")
        expiry_date_raw = override.get("expiry_date")
        batch_number = override.get("batch_number") or default_batch_number

        if manufacture_date_raw:
            manufacture_date = parse_date(manufacture_date_raw)
            if manufacture_date is None:
                results["skipped"].append(
                    {
                        "movement_id": str(movement.id),
                        "reason": "invalid_manufacture_date",
                    }
                )
                continue
        else:
            manufacture_date = default_manufacture_date or timezone.now().date()

        if expiry_date_raw:
            expiry_date = parse_date(expiry_date_raw)
            if expiry_date is None:
                results["skipped"].append(
                    {
                        "movement_id": str(movement.id),
                        "reason": "invalid_expiry_date",
                    }
                )
                continue
        else:
            expiry_date = default_expiry_date

        if expiry_date is None and product.shelf_life_days:
            expiry_date = manufacture_date + timezone.timedelta(
                days=product.shelf_life_days
            )

        if movement.total_quantity is None:
            results["skipped"].append(
                {"movement_id": str(movement.id), "reason": "missing_quantity"}
            )
            continue

        with transaction.atomic():
            batch_payload = {
                "product": product,
                "warehouse": movement.warehouse,
                "quantity": Decimal("0"),
                "manufacture_date": manufacture_date,
                "expiry_date": expiry_date,
            }
            if batch_number:
                batch_payload["batch_number"] = batch_number

            batch = Batch.objects.create(**batch_payload)

            StockMovementBatch.objects.create(
                stock_movement=movement,
                batch=batch,
                quantity=movement.total_quantity,
            )

        results["created"].append(
            {"movement_id": str(movement.id), "batch_id": str(batch.id)}
        )

    results["checked"] = movements.count()
    results["created_count"] = len(results["created"])
    results["skipped_count"] = len(results["skipped"])
    return results
