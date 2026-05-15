"""
DispatchService — physically moves goods out of the warehouse.

Responsibilities:
  - Hard stock check before dispatch
  - FEFO batch selection (earliest expiry first)
  - Creates Delivery + DeliveryLine records
  - Posts StockMovement (OUT) per batch allocation
  - Snapshots cost_per_unit from CostingEntry onto SalesOrderLine
  - Computes cogs_total and posts a COGS JournalEntry
  - Updates SalesOrderLine.quantity_dispatched
  - Advances SalesOrder status
"""

from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import SYSTEM_KEY_COGS, SYSTEM_KEY_INVENTORY_RAW
from apps.costing.models import CostingEntry
from apps.finance.services.journal_service import JournalLine, JournalService
from apps.inventory.models import Batch, Stock, StockMovement, StockMovementBatch
from apps.sales.models import Delivery, DeliveryLine, SalesOrder, SalesOrderLine
from central.models import Product, Warehouse


class DispatchService:

    @staticmethod
    @transaction.atomic
    def dispatch_order(
        order: SalesOrder,
        created_by,
        dispatched_at: datetime | None = None,
    ) -> Delivery:
        """
        Dispatch all (or remaining) lines on a confirmed order.

        Returns the created Delivery record.
        """
        if order.status not in ("confirmed", "picking"):
            raise ValidationError(
                f"Only confirmed or picking orders can be dispatched "
                f"(current status: {order.status}).",
                code="invalid_dispatch_status",
            )

        if dispatched_at is None:
            dispatched_at = timezone.now()

        lines = list(order.lines.select_related("product").all())

        # Hard stock check for every line
        for line in lines:
            remaining = line.quantity - line.quantity_dispatched
            if remaining <= 0:
                continue
            available = DispatchService._available_stock(order.warehouse, line.product)
            if available < remaining:
                raise ValidationError(
                    f"Insufficient stock for '{line.product.name}': "
                    f"need {remaining}, available {available}.",
                    code="insufficient_stock",
                )

        # Create the Delivery header
        delivery = Delivery(
            sales_order=order,
            warehouse=order.warehouse,
            status="in_transit",
            dispatched_at=dispatched_at,
            created_by=created_by,
        )
        delivery.save()

        # Process each line
        for line in lines:
            remaining = line.quantity - line.quantity_dispatched
            if remaining <= 0:
                continue
            DispatchService._dispatch_line(delivery, line, remaining, order.warehouse)

        # Advance order status
        all_dispatched = all(
            ln.quantity_dispatched >= ln.quantity for ln in order.lines.all()
        )
        order.status = "dispatched" if all_dispatched else "confirmed"
        order.save(update_fields=["status", "updated_at"])

        return delivery

    # ------------------------------------------------------------------ #
    # Line-level dispatch                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _dispatch_line(
        delivery: Delivery,
        line: SalesOrderLine,
        qty_to_dispatch: Decimal,
        warehouse: Warehouse,
    ) -> None:
        """
        Allocate qty_to_dispatch across FEFO batches, create DeliveryLines,
        post StockMovements, snapshot cost, and update quantity_dispatched.
        """
        batches = DispatchService._fefo_batches(
            warehouse, line.product, qty_to_dispatch
        )

        cost_per_unit = DispatchService._resolve_cost(line.product, warehouse)

        remaining = qty_to_dispatch
        for batch, batch_qty in batches:
            if remaining <= 0:
                break
            allocated = min(batch_qty, remaining)

            # DeliveryLine
            dl = DeliveryLine(
                delivery=delivery,
                sales_order_line=line,
                product=line.product,
                batch=batch,
                quantity_delivered=allocated,
            )
            dl.save()

            # StockMovement
            movement = StockMovement(
                warehouse=warehouse,
                movement_type="OUT",
                total_quantity=allocated,
                reference_number=delivery.sales_order.order_number,
                notes=f"Sale — {delivery.delivery_number}",
            )
            movement.save()
            StockMovementBatch.objects.create(
                stock_movement=movement,
                batch=batch,
                quantity=allocated,
            )

            # Deduct from batch and stock
            batch.quantity -= allocated
            batch.save(update_fields=["quantity"])

            Stock.objects.filter(product=line.product, warehouse=warehouse).update(
                quantity_on_hand=Stock.objects.filter(
                    product=line.product, warehouse=warehouse
                ).values_list("quantity_on_hand", flat=True)[0]
                - allocated
            )

            remaining -= allocated

        # Update SalesOrderLine
        line.quantity_dispatched += qty_to_dispatch
        if cost_per_unit is not None:
            line.cost_per_unit = cost_per_unit
            line.cogs_total = line.quantity_dispatched * cost_per_unit
        line.save(update_fields=["quantity_dispatched", "cost_per_unit", "cogs_total"])

        # Post COGS journal entry
        if cost_per_unit is not None:
            cogs_amount = qty_to_dispatch * cost_per_unit
            DispatchService._post_cogs_journal(
                order=delivery.sales_order,
                product=line.product,
                cogs_amount=cogs_amount,
                created_by=delivery.created_by,
            )

    # ------------------------------------------------------------------ #
    # FEFO batch selection                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fefo_batches(
        warehouse: Warehouse,
        product: Product,
        qty_needed: Decimal,
    ) -> list[tuple[Batch, Decimal]]:
        """
        Return a list of (batch, quantity) tuples ordered by earliest expiry.
        Splits across multiple batches if needed.
        """
        batches = Batch.objects.filter(
            product=product,
            warehouse=warehouse,
            quantity__gt=0,
        ).order_by(
            "expiry_date"
        )  # nulls last by default — treat no-expiry as last

        allocations = []
        remaining = qty_needed
        for batch in batches:
            if remaining <= 0:
                break
            take = min(batch.quantity, remaining)
            allocations.append((batch, take))
            remaining -= take

        if remaining > 0:
            raise ValidationError(
                f"Could not allocate full quantity from available batches "
                f"(short by {remaining}).",
                code="batch_allocation_failed",
            )

        return allocations

    # ------------------------------------------------------------------ #
    # Cost snapshot                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_cost(product: Product, warehouse: Warehouse) -> Decimal | None:
        """
        Return cost_per_unit from the most recent CostingEntry for this
        product/warehouse combination. Returns None if no entry exists.
        """
        entry = (
            CostingEntry.objects.filter(product=product, warehouse=warehouse)
            .order_by("-computed_at")
            .first()
        )
        return entry.cost_per_unit if entry else None

    # ------------------------------------------------------------------ #
    # COGS journal entry                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _post_cogs_journal(
        order: SalesOrder,
        product: Product,
        cogs_amount: Decimal,
        created_by,
    ) -> None:
        """
        Debit COGS account, Credit Inventory account.
        Uses JournalService for period validation and balancing guarantees.
        """
        company = order.warehouse.company
        cogs_account = JournalService.get_account(
            company=company,
            system_key=SYSTEM_KEY_COGS,
            fallback_code="5000",
        )
        inventory_account = JournalService.get_account(
            company=company,
            system_key=SYSTEM_KEY_INVENTORY_RAW,
            fallback_code="1200",
        )

        JournalService.post(
            company=company,
            entry_date=timezone.now().date(),
            description=f"COGS — {product.name} dispatched on {order.order_number}",
            lines=[
                JournalLine(
                    account_code=cogs_account.code,
                    type="debit",
                    amount=cogs_amount,
                    description=f"COGS {product.name}",
                ),
                JournalLine(
                    account_code=inventory_account.code,
                    type="credit",
                    amount=cogs_amount,
                    description=f"Inventory reduction {product.name}",
                ),
            ],
            reference_type="SalesOrder",
            reference_id=order.id,
            created_by=created_by,
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _available_stock(warehouse: Warehouse, product: Product) -> Decimal:
        try:
            return Stock.objects.get(
                product=product, warehouse=warehouse
            ).quantity_on_hand
        except Stock.DoesNotExist:
            return Decimal("0")
