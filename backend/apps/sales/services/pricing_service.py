"""
PricingService — resolves the correct unit price for a product on an order line.

Rules:
  POS  → ProductPricingRule.recommended_selling_price (no negotiation)
  B2B  → CustomerProduct agreed price if active, else recommended_selling_price
  Both → price must be >= ProductPricingRule.minimum_selling_price
         if below, raise PriceBelowFloorError (requires manager approval)
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.costing.models import ProductPricingRule
from apps.sales.models import Customer, CustomerProduct
from central.models import Product


class PriceBelowFloorError(ValidationError):
    """Raised when a resolved price is below the minimum selling price."""
    pass


class NoPricingRuleError(ValidationError):
    """Raised when no ProductPricingRule exists for a product."""
    pass


class PricingService:

    @staticmethod
    def resolve_price(
        product: Product,
        customer: Customer,
        order_type: str,
        today: date | None = None,
    ) -> Decimal:
        """
        Resolve and return the unit price for this product/customer/order_type.

        Raises:
            NoPricingRuleError  — no ProductPricingRule exists for the product
            PriceBelowFloorError — resolved price is below minimum_selling_price
        """
        if today is None:
            today = date.today()

        rule = PricingService._get_pricing_rule(product)

        if order_type == "pos":
            price = rule.recommended_selling_price
        else:
            price = PricingService._b2b_price(product, customer, rule, today)

        PricingService._check_floor(price, rule, product)
        return price

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_pricing_rule(product: Product) -> ProductPricingRule:
        try:
            return ProductPricingRule.objects.select_related("product").get(product=product)
        except ProductPricingRule.DoesNotExist:
            raise NoPricingRuleError(
                f"No pricing rule defined for product '{product.name}'. "
                "Cannot add this product to an order.",
                code="no_pricing_rule",
            )

    @staticmethod
    def _b2b_price(
        product: Product,
        customer: Customer,
        rule: ProductPricingRule,
        today: date,
    ) -> Decimal:
        """Return the active CustomerProduct price, or fall back to recommended."""
        agreement = (
            CustomerProduct.objects.filter(
                customer=customer,
                product=product,
                is_active=True,
                valid_from__lte=today,
            )
            .filter(
                # valid_until is optional — null means open-ended
                models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=today)
            )
            .order_by("-valid_from")
            .first()
        )
        if agreement:
            return agreement.unit_price
        return rule.recommended_selling_price

    @staticmethod
    def _check_floor(price: Decimal, rule: ProductPricingRule, product: Product) -> None:
        if rule.minimum_selling_price is None:
            return
        if price < rule.minimum_selling_price:
            raise PriceBelowFloorError(
                f"Price {price} for '{product.name}' is below the minimum "
                f"selling price {rule.minimum_selling_price}. "
                "Manager approval is required before this order can be confirmed.",
                code="price_below_floor",
            )


# Make models.Q available without a top-level import that would cause
# circular issues in some Django setups.
from django.db import models  # noqa: E402 — intentional late import
