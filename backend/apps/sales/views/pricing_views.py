from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.costing.models import ProductPricingRule
from apps.inventory.models import Stock
from apps.sales.models import Customer
from apps.sales.serializers.pricing_serializers import ResolvePriceSerializer, ResolvedPriceSerializer
from apps.sales.services.customer_service import CustomerService
from apps.sales.services.pricing_service import NoPricingRuleError, PriceBelowFloorError, PricingService
from central.models import Product, Warehouse


class ResolvePriceView(APIView):
    """
    GET /sales/pricing/resolve?customer_id=&product_id=&warehouse_id=

    Returns the resolved unit price for a customer + product combination,
    the source of the price, floor check result, and current stock level.
    Called by the order UI every time a product is added to an order.

    customer_id is optional — omit it for walk-in / anonymous customers.
    The endpoint will fall back to the Cash Customer record in that case,
    which always resolves prices from the product pricing rule (POS path).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ResolvePriceSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Fall back to Cash Customer for walk-in / anonymous customers
        if data.get("customer_id"):
            customer = get_object_or_404(Customer, pk=data["customer_id"])
        else:
            customer = CustomerService.get_or_create_cash_customer()
        product = get_object_or_404(Product, pk=data["product_id"])
        warehouse = get_object_or_404(Warehouse, pk=data["warehouse_id"])

        order_type = "pos" if customer.customer_type == "retail" else "b2b"

        # Resolve price — catch floor errors to still return useful data
        below_floor = False
        try:
            resolved_price = PricingService.resolve_price(
                product=product, customer=customer, order_type=order_type
            )
        except PriceBelowFloorError as exc:
            # Price resolved but is below floor — return it with flag
            below_floor = True
            # Re-resolve without floor check to get the raw price
            from apps.costing.models import ProductPricingRule as PPR
            from apps.sales.models import CustomerProduct
            from datetime import date
            today = date.today()
            try:
                rule = PPR.objects.get(product=product)
                if order_type == "pos":
                    resolved_price = rule.recommended_selling_price
                else:
                    from django.db.models import Q
                    agreement = (
                        CustomerProduct.objects.filter(
                            customer=customer, product=product, is_active=True,
                            valid_from__lte=today,
                        )
                        .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=today))
                        .order_by("-valid_from")
                        .first()
                    )
                    resolved_price = agreement.unit_price if agreement else rule.recommended_selling_price
            except PPR.DoesNotExist:
                return Response({"detail": str(exc)}, status=422)
        except NoPricingRuleError as exc:
            return Response({"detail": str(exc)}, status=422)

        # Determine price source
        from apps.sales.models import CustomerProduct
        from datetime import date
        today = date.today()
        from django.db.models import Q
        has_agreement = (
            order_type == "b2b"
            and CustomerProduct.objects.filter(
                customer=customer, product=product, is_active=True,
                valid_from__lte=today,
            )
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=today))
            .exists()
        )
        price_source = "agreement" if has_agreement else "pricing_rule"

        # Pricing rule metadata
        try:
            rule = ProductPricingRule.objects.get(product=product)
            min_price = rule.minimum_selling_price
            rec_price = rule.recommended_selling_price
        except ProductPricingRule.DoesNotExist:
            min_price = None
            rec_price = None

        # Stock
        try:
            stock_qty = Stock.objects.get(product=product, warehouse=warehouse).quantity_on_hand
        except Stock.DoesNotExist:
            stock_qty = Decimal("0")

        result = {
            "product_id": product.id,
            "product_name": product.name,
            "customer_id": customer.id,
            "order_type": order_type,
            "resolved_price": resolved_price,
            "price_source": price_source,
            "minimum_selling_price": min_price,
            "recommended_selling_price": rec_price,
            "below_floor": below_floor,
            "stock_available": stock_qty,
            "sufficient_stock": stock_qty > 0,
        }
        return Response(ResolvedPriceSerializer(result).data)
