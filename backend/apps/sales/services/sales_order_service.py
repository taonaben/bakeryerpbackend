"""
SalesOrderService — full lifecycle of a SalesOrder.

Handles creation, line management, confirmation, the POS fast path,
and cancellation. Delegates to PricingService, CustomerService,
DispatchService, InvoiceService, and PaymentService where needed.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import Stock
from apps.sales.models import Customer, SalesOrder, SalesOrderLine
from apps.sales.services.customer_service import CustomerService
from apps.sales.services.pricing_service import PricingService
from central.models import Product, Warehouse


class SalesOrderService:

    # ------------------------------------------------------------------ #
    # Create                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    @transaction.atomic
    def create_order(
        customer: Customer,
        warehouse: Warehouse,
        created_by,
        order_date=None,
        **kwargs,
    ) -> SalesOrder:
        """
        Create a new SalesOrder in draft status.

        - Validates customer is active.
        - Derives order_type from customer_type.
        - B2B: runs credit check (order total is 0 at creation — checked again at confirm).
        """
        if not customer.is_active:
            raise ValidationError(
                f"Customer '{customer.name}' is inactive. Cannot create an order.",
                code="inactive_customer",
            )

        order_type = "pos" if customer.customer_type == "retail" else "b2b"

        order = SalesOrder(
            customer=customer,
            warehouse=warehouse,
            order_type=order_type,
            status="draft",
            order_date=order_date or timezone.now(),
            created_by=created_by,
            **kwargs,
        )
        order.save()
        return order

    # ------------------------------------------------------------------ #
    # Lines                                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    @transaction.atomic
    def add_line(
        order: SalesOrder,
        product: Product,
        quantity: Decimal,
    ) -> SalesOrderLine:
        """
        Add a product line to a draft order.

        - Resolves unit price via PricingService.
        - Checks stock availability (soft check — flags but does not block B2B).
        - Recomputes order totals.
        """
        if order.status != "draft":
            raise ValidationError(
                "Lines can only be added to orders in draft status.",
                code="order_not_draft",
            )

        unit_price = PricingService.resolve_price(
            product=product,
            customer=order.customer,
            order_type=order.order_type,
        )

        line = SalesOrderLine(
            sales_order=order,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            subtotal=quantity * unit_price,
        )

        # Stock availability check
        stock_ok = SalesOrderService._has_sufficient_stock(order.warehouse, product, quantity)
        if not stock_ok:
            if order.order_type == "pos":
                raise ValidationError(
                    f"Insufficient stock for '{product.name}' in warehouse "
                    f"'{order.warehouse.name}'. POS sales require available stock.",
                    code="insufficient_stock_pos",
                )
            # B2B: flag but allow
            line._stock_warning = (
                f"Warning: insufficient stock for '{product.name}'. "
                "Stock will be hard-checked at dispatch time."
            )

        line.save()
        SalesOrderService._recompute_totals(order)
        return line

    @staticmethod
    @transaction.atomic
    def remove_line(order: SalesOrder, line: SalesOrderLine) -> None:
        if order.status != "draft":
            raise ValidationError(
                "Lines can only be removed from orders in draft status.",
                code="order_not_draft",
            )
        line.delete()
        SalesOrderService._recompute_totals(order)

    # ------------------------------------------------------------------ #
    # Confirm                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    @transaction.atomic
    def confirm_order(order: SalesOrder) -> SalesOrder:
        """
        Confirm a draft order.

        - Locks all line prices (they are already snapshotted; no further action needed).
        - B2B: runs credit check against the full order total.
        - POS: hard stock check, then triggers the fast path.
        """
        if order.status != "draft":
            raise ValidationError(
                f"Only draft orders can be confirmed (current status: {order.status}).",
                code="invalid_status_transition",
            )

        if order.order_type == "b2b":
            CustomerService.check_credit(order.customer, order.total_amount)

        if order.order_type == "pos":
            # Hard stock check for POS
            for line in order.lines.select_related("product").all():
                if not SalesOrderService._has_sufficient_stock(
                    order.warehouse, line.product, line.quantity
                ):
                    raise ValidationError(
                        f"Insufficient stock for '{line.product.name}'. "
                        "POS orders cannot be confirmed without available stock.",
                        code="insufficient_stock_pos",
                    )

        order.status = "confirmed"
        order.save(update_fields=["status", "updated_at"])

        if order.order_type == "pos":
            SalesOrderService._pos_fast_path(order)

        return order

    # ------------------------------------------------------------------ #
    # Cancel                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    @transaction.atomic
    def cancel_order(order: SalesOrder, cancelled_by, reason: str = "") -> SalesOrder:
        """
        Cancel an order. Only allowed before dispatched status.
        """
        if order.status in ("dispatched", "invoiced", "paid"):
            raise ValidationError(
                "Cannot cancel an order that has already been dispatched. "
                "Use the returns/credit note process instead.",
                code="cancellation_blocked",
            )

        order.status = "cancelled"
        order.notes = (
            f"{order.notes or ''}\n[Cancelled by {cancelled_by} — {reason}]".strip()
        )
        order.save(update_fields=["status", "notes", "updated_at"])
        return order

    # ------------------------------------------------------------------ #
    # POS fast path                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _pos_fast_path(order: SalesOrder) -> None:
        """
        Atomic POS completion: dispatch → invoice → payment in one transaction.
        The wrapping confirm_order transaction ensures full rollback on any failure.
        """
        from apps.sales.services.dispatch_service import DispatchService
        from apps.sales.services.invoice_service import InvoiceService
        from apps.sales.services.payment_service import PaymentService
        from django.utils import timezone

        dispatch = DispatchService.dispatch_order(
            order=order,
            created_by=order.created_by,
            dispatched_at=timezone.now(),
        )

        invoice = InvoiceService.create_invoice(
            order=order,
            created_by=order.created_by,
        )

        PaymentService.record_payment(
            invoice=invoice,
            amount=invoice.total_amount,
            payment_method="cash",
            received_by=order.created_by,
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _has_sufficient_stock(warehouse, product: Product, quantity: Decimal) -> bool:
        try:
            stock = Stock.objects.get(product=product, warehouse=warehouse)
            return stock.quantity_on_hand >= quantity
        except Stock.DoesNotExist:
            return False

    @staticmethod
    def _recompute_totals(order: SalesOrder) -> None:
        from django.db.models import Sum
        agg = order.lines.aggregate(subtotal=Sum("subtotal"))
        subtotal = agg["subtotal"] or Decimal("0")
        # Tax computation placeholder — extend when tax rules are defined
        tax_amount = Decimal("0")
        order.subtotal = subtotal
        order.tax_amount = tax_amount
        order.total_amount = subtotal + tax_amount
        order.save(update_fields=["subtotal", "tax_amount", "total_amount", "updated_at"])
