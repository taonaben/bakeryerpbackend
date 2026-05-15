from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin
from apps.costing.models import ProductPricingRule
from apps.costing.serializers.pricing_rule_serializers import (
    ProductPricingRuleSerializer,
    ProductPricingRuleWriteSerializer,
)


class ProductPricingRuleViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """
    CRUD for ProductPricingRule. Prices are computed, not entered manually.

    list:        GET  /pricing-rules
    retrieve:    GET  /pricing-rules/{id}
    create:      POST /pricing-rules
    partial_update: PATCH /pricing-rules/{id}
    recalculate: POST /pricing-rules/{id}/recalculate
    """

    permission_classes = [IsAuthenticated]
    queryset = ProductPricingRule.objects.select_related(
        "product", "standard_cost_reference", "updated_by"
    )
    company_field = "product__company"
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action in ("create", "partial_update"):
            return ProductPricingRuleWriteSerializer
        return ProductPricingRuleSerializer

    @action(detail=True, methods=["post"], url_path="recalculate")
    def recalculate(self, request, pk=None):
        """
        POST /pricing-rules/{id}/recalculate

        Re-runs ProductPricingRuleUpdater against the latest StandardCost
        for this product. Useful when management changes margin targets.
        """
        from apps.costing.models import StandardCost
        from apps.costing.services.product_pricing_rule_updater import ProductPricingRuleUpdater

        rule = self.get_object()

        latest_sc = (
            StandardCost.objects.filter(product=rule.product)
            .order_by("-computed_at")
            .first()
        )
        if latest_sc is None:
            return Response(
                {"detail": "No StandardCost found for this product. Approve a formula first."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            updater = ProductPricingRuleUpdater(
                standard_cost=latest_sc,
                updated_by=request.user,
            )
            rule = updater.run()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ProductPricingRuleSerializer(rule).data)
