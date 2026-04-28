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

from apps.accounting.models import Account, JournalEntry, JournalEntryLine
from apps.costing.models import CostingEntry
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
            ln.quantity_dispatched >= ln.quantity
            for ln in order.lines.all()
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
        batches = DispatchService._fefo_batches(warehouse, line.product, qty_to_dispatch)

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

            Stock.objects.filter(
                product=line.product, warehouse=warehouse
            ).update(quantity_on_hand=Stock.objects.filter(
                product=line.product, warehouse=warehouse
            ).values_list("quantity_on_hand", flat=True)[0] - allocated)

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
        batches = (
            Batch.objects.filter(
                product=product,
                warehouse=warehouse,
                quantity__gt=0,
            )
            .order_by("expiry_date")  # nulls last by default — treat no-expiry as last
        )

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
        Accounts are looked up by code on the company attached to the warehouse.
        Silently skips if accounts are not configured.
        """
        try:
            company = order.warehouse.company
            cogs_account = Account.objects.get(company=company, code="5000")   # COGS
            inventory_account = Account.objects.get(company=company, code="1200")  # Inventory
        except Account.DoesNotExist:
            # Accounting chart not yet configured — skip silently
            return

        je = JournalEntry.objects.create(
            company=company,
            entry_date=timezone.now().date(),
            reference=order.order_number,
            description=f"COGS — {product.name} dispatched on {order.order_number}",
            source_type="SalesOrder",
            source_id=order.id,
            created_by=created_by,
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=cogs_account,
            debit=cogs_amount,
            credit=Decimal("0"),
            description=f"COGS {product.name}",
        )
        JournalEntryLine.objects.create(
            journal_entry=je,
            account=inventory_account,
            debit=Decimal("0"),
            credit=cogs_amount,
            description=f"Inventory reduction {product.name}",
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _available_stock(warehouse: Warehouse, product: Product) -> Decimal:
        try:
            return Stock.objects.get(product=product, warehouse=warehouse).quantity_on_hand
        except Stock.DoesNotExist:
            return Decimal("0")
