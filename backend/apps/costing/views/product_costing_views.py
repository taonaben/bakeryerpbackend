"""
Cross-module product-scoped endpoints.

  GET /products/{product_id}/standard-cost/latest
  GET /products/{product_id}/pricing-rule
  GET /production/batches/{batch_id}/costing-entry
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.costing.models import CostingEntry, StandardCost, ProductPricingRule
from apps.costing.serializers.standard_cost_serializers import StandardCostSerializer
from apps.costing.serializers.costing_entry_serializers import CostingEntrySerializer
from apps.costing.serializers.pricing_rule_serializers import ProductPricingRuleSerializer


class ProductLatestStandardCostView(APIView):
    """
    GET /products/{product_id}/standard-cost/latest

    Returns the most recent StandardCost for a product.
    Used by the sales module when setting CustomerProduct prices.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, product_id):
        sc = (
            StandardCost.objects.filter(product_id=product_id)
            .select_related("formula", "product", "overhead_rate", "computed_by")
            .prefetch_related("lines", "lines__product")
            .order_by("-computed_at")
            .first()
        )
        if sc is None:
            return Response(
                {"detail": "No StandardCost found for this product."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(StandardCostSerializer(sc).data)


class ProductPricingRuleDetailView(APIView):
    """
    GET /products/{product_id}/pricing-rule

    Returns the ProductPricingRule for a product.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, product_id):
        try:
            rule = ProductPricingRule.objects.select_related(
                "product", "standard_cost_reference", "updated_by"
            ).get(product_id=product_id)
        except ProductPricingRule.DoesNotExist:
            return Response(
                {"detail": "No pricing rule found for this product."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ProductPricingRuleSerializer(rule).data)


class BatchCostingEntryView(APIView):
    """
    GET /production/batches/{batch_id}/costing-entry

    Returns the CostingEntry for a specific production batch.
    Natural entry point from the production module after a batch closes.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, batch_id):
        try:
            entry = CostingEntry.objects.select_related(
                "production_batch", "product", "warehouse", "standard_cost", "overhead_rate"
            ).prefetch_related("lines", "lines__product").get(
                production_batch_id=batch_id
            )
        except CostingEntry.DoesNotExist:
            return Response(
                {"detail": "No CostingEntry found for this batch."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(CostingEntrySerializer(entry).data)
