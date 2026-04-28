"""
CustomerService — manages customer lifecycle and credit checks.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.sales.models import Customer


CASH_CUSTOMER_NAME = "Cash Customer"


class CustomerService:

    @staticmethod
    def get_or_create_cash_customer() -> Customer:
        """Return the permanent Cash Customer record, creating it if absent."""
        customer, _ = Customer.objects.get_or_create(
            name=CASH_CUSTOMER_NAME,
            defaults={
                "customer_type": "retail",
                "payment_terms": "cash",
                "is_active": True,
            },
        )
        return customer

    @staticmethod
    @transaction.atomic
    def create_customer(data: dict) -> Customer:
        """
        Create a new customer.

        For retail: only name is required.
        For business: payment_terms must be explicitly provided.
        """
        customer_type = data.get("customer_type", "retail")

        if customer_type == "business" and not data.get("payment_terms"):
            raise ValidationError(
                "payment_terms must be explicitly set for business customers.",
                code="missing_payment_terms",
            )

        customer = Customer(**data)
        customer.full_clean()
        customer.save()
        return customer

    @staticmethod
    @transaction.atomic
    def update_customer(customer: Customer, data: dict) -> Customer:
        """
        Update a customer record.

        - Changing payment_terms does NOT affect existing unpaid invoices.
        - Lowering credit_limit flags the account if already over limit but
          does not cancel existing orders.
        - Setting is_active=False blocks new orders only.
        """
        if customer.name == CASH_CUSTOMER_NAME:
            raise ValidationError(
                "The Cash Customer system record cannot be modified.",
                code="protected_record",
            )

        new_credit_limit = data.get("credit_limit", customer.credit_limit)
        for field, value in data.items():
            setattr(customer, field, value)

        customer.full_clean()
        customer.save()

        # Flag account if now over the new credit limit
        if (
            customer.customer_type == "business"
            and new_credit_limit is not None
        ):
            outstanding = CustomerService._outstanding_balance(customer)
            if outstanding > new_credit_limit:
                # Return a warning alongside the saved customer — callers
                # should surface this to the user.
                customer._credit_limit_warning = (
                    f"Customer is currently over the new credit limit "
                    f"(outstanding: {outstanding}, limit: {new_credit_limit})."
                )

        return customer

    @staticmethod
    def deactivate_customer(customer: Customer) -> Customer:
        """Set is_active=False. Existing orders are unaffected."""
        if customer.name == CASH_CUSTOMER_NAME:
            raise ValidationError(
                "The Cash Customer system record cannot be deactivated.",
                code="protected_record",
            )
        customer.is_active = False
        customer.save(update_fields=["is_active"])
        return customer

    @staticmethod
    def check_credit(customer: Customer, new_order_total: Decimal) -> None:
        """
        Called by SalesOrderService before confirming a B2B order.

        Raises ValidationError if the new order would push the customer over
        their credit limit. Retail and cash customers always pass.
        """
        if customer.customer_type == "retail":
            return
        if customer.name == CASH_CUSTOMER_NAME:
            return
        if customer.credit_limit is None:
            return  # No limit set — unlimited credit

        outstanding = CustomerService._outstanding_balance(customer)
        if outstanding + new_order_total > customer.credit_limit:
            raise ValidationError(
                f"Order blocked: customer credit limit exceeded. "
                f"Outstanding balance: {outstanding}, "
                f"New order: {new_order_total}, "
                f"Limit: {customer.credit_limit}.",
                code="credit_limit_exceeded",
            )

    @staticmethod
    def _outstanding_balance(customer: Customer) -> Decimal:
        """Sum of all unpaid, non-cancelled invoice totals for this customer."""
        from django.db.models import Sum
        from apps.sales.models import Invoice

        result = (
            Invoice.objects.filter(
                sales_order__customer=customer,
            )
            .exclude(status__in=["paid", "cancelled"])
            .aggregate(total=Sum("total_amount"))["total"]
        )
        return result or Decimal("0")
