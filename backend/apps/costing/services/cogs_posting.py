"""
COGSPostingService
==================
Triggered when a SalesOrder is confirmed or shipped.

Responsibilities:
  1. For each sales order line, resolve the actual cost rate (CostingEntry
     or StandardCost fallback).
  2. Compute COGS, revenue, and gross profit per line.
  3. Post a balanced JournalEntry (debit COGS / credit Inventory).
"""

import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import SYSTEM_KEY_COGS, SYSTEM_KEY_INVENTORY_RAW
from apps.costing.models import CostingEntry, StandardCost
from apps.finance.services.journal_service import JournalLine, JournalService

logger = logging.getLogger(__name__)

# Account code fallback values if system-key lookup is unavailable.
ACCOUNT_COGS = "5000"
ACCOUNT_INVENTORY = "1200"


class COGSPostingError(Exception):
    """Raised when a COGS post cannot be completed."""


class COGSPostingService:
    """
    Post COGS journal entries for a confirmed/shipped SalesOrder.

    Usage::

        service = COGSPostingService(sales_order=order, posted_by=request.user)
        result = service.run()

    Returns a list of dicts::

        [
            {
                "line": <SalesOrderLine>,
                "cogs": Decimal,
                "revenue": Decimal,
                "gross_profit": Decimal,
                "cost_source": "actual" | "standard_estimated",
                "journal_entry": <JournalEntry>,
            },
            ...
        ]
    """

    def __init__(self, sales_order, posted_by=None):
        self.order = sales_order
        self.posted_by = posted_by

    @transaction.atomic
    def run(self) -> list:
        results = []

        for line in self._order_lines():
            result = self._process_line(line)
            results.append(result)

        return results

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _order_lines(self):
        """
        Return the line items of the sales order.
        Supports both a .lines and .line_items related manager name.
        """
        if hasattr(self.order, "lines"):
            return self.order.lines.select_related("product").all()
        if hasattr(self.order, "line_items"):
            return self.order.line_items.select_related("product").all()
        raise COGSPostingError(
            f"SalesOrder {self.order} has no recognised line-item relation."
        )

    def _process_line(self, line) -> dict:
        product = line.product
        warehouse = getattr(self.order, "warehouse", None)
        quantity = Decimal(str(line.quantity))
        unit_price = Decimal(str(line.unit_price))

        cost_per_unit, cost_source = self._resolve_cost(product, warehouse)

        cogs = (quantity * cost_per_unit).quantize(Decimal("0.01"))
        revenue = (quantity * unit_price).quantize(Decimal("0.01"))
        gross_profit = revenue - cogs

        journal_entry = self._post_journal(line, cogs, warehouse)

        if cost_source == "standard_estimated":
            logger.info(
                "COGS for product '%s' on order %s used estimated StandardCost "
                "(no CostingEntry found). COGS=%s",
                product.name,
                self.order,
                cogs,
            )

        return {
            "line": line,
            "cogs": cogs,
            "revenue": revenue,
            "gross_profit": gross_profit,
            "cost_source": cost_source,
            "journal_entry": journal_entry,
        }

    def _resolve_cost(self, product, warehouse):
        """
        Return (cost_per_unit: Decimal, source: str).

        Priority:
          1. Most recent completed CostingEntry for this product + warehouse.
          2. Most recent StandardCost for this product (estimated fallback).
          3. Raise COGSPostingError.
        """
        # 1. Actual cost from a completed batch
        qs = CostingEntry.objects.filter(product=product)
        if warehouse:
            qs = qs.filter(warehouse=warehouse)
        entry = qs.order_by("-computed_at").first()
        if entry:
            return entry.cost_per_unit, "actual"

        # 2. Standard cost fallback
        sc = (
            StandardCost.objects.filter(product=product)
            .order_by("-computed_at")
            .first()
        )
        if sc:
            return sc.total_standard_cost_per_unit, "standard_estimated"

        raise COGSPostingError(
            f"No cost data found for product '{product.name}'. "
            "Cannot post COGS without a CostingEntry or StandardCost."
        )

    def _post_journal(self, line, cogs: Decimal, warehouse):
        """
        Post a balanced journal entry:
          Dr  COGS (5000)       cogs
          Cr  Inventory (1200)  cogs
        """
        product = line.product
        company = product.company
        description = (
            f"COGS for {product.name} × {line.quantity} "
            f"on order {getattr(self.order, 'order_number', self.order.pk)}"
        )

        cogs_account = JournalService.get_account(
            company=company,
            system_key=SYSTEM_KEY_COGS,
            fallback_code=ACCOUNT_COGS,
        )
        inventory_account = JournalService.get_account(
            company=company,
            system_key=SYSTEM_KEY_INVENTORY_RAW,
            fallback_code=ACCOUNT_INVENTORY,
        )

        return JournalService.post(
            company=company,
            entry_date=timezone.now().date(),
            description=description,
            reference_type="sales_order_line",
            reference_id=line.id,
            lines=[
                JournalLine(
                    account_code=cogs_account.code,
                    type="debit",
                    amount=cogs,
                    description=description,
                ),
                JournalLine(
                    account_code=inventory_account.code,
                    type="credit",
                    amount=cogs,
                    description=description,
                ),
            ],
            created_by=self.posted_by,
        )
