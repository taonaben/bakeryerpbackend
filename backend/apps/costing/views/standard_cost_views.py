from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin
from apps.costing.models import StandardCost, StandardCostLine
from apps.costing.serializers.standard_cost_serializers import (
    ComputeStandardCostSerializer,
    StandardCostLineSerializer,
    StandardCostListSerializer,
    StandardCostSerializer,
)


class StandardCostViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    """
    Read-only access to StandardCost records.
    Write access is exclusively via the compute action.

    list:     GET /standard-costs
    retrieve: GET /standard-costs/{id}
    lines:    GET /standard-costs/{id}/lines
    compute:  POST /standard-costs/compute
    """

    permission_classes = [IsAuthenticated]
    queryset = StandardCost.objects.select_related(
        "formula", "product", "overhead_rate", "computed_by"
    ).prefetch_related("lines", "lines__product", "lines__supplier_product_used__supplier")
    company_field = "product__company"

    def get_serializer_class(self):
        if self.action == "list":
            return StandardCostListSerializer
        return StandardCostSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        product_id = self.request.query_params.get("product_id")
        formula_id = self.request.query_params.get("formula_id")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if product_id:
            qs = qs.filter(product_id=product_id)
        if formula_id:
            qs = qs.filter(formula_id=formula_id)
        if date_from:
            qs = qs.filter(computed_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(computed_at__date__lte=date_to)

        return qs.order_by("-computed_at")

    @action(detail=True, methods=["get"], url_path="lines")
    def lines(self, request, pk=None):
        """GET /standard-costs/{id}/lines — ingredient-level breakdown."""
        standard_cost = self.get_object()
        lines = StandardCostLine.objects.filter(
            standard_cost=standard_cost
        ).select_related("product", "formula_line", "supplier_product_used__supplier")
        return Response(StandardCostLineSerializer(lines, many=True).data)

    @action(detail=False, methods=["post"], url_path="compute")
    def compute(self, request):
        """
        POST /standard-costs/compute
        Body: { "formula_id": "<uuid>", "warehouse_id": "<uuid>" }

        Runs StandardCostEngine. Idempotent — returns existing record if already computed.
        """
        serializer = ComputeStandardCostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.formulation.models import Formula
        from central.models import Warehouse
        from apps.costing.services.standard_cost_engine import (
            WarehouseStandardCostEngine,
            NoOverheadRateError,
            NoPricedIngredientError,
        )

        formula = Formula.objects.get(pk=serializer.validated_data["formula_id"])
        warehouse = Warehouse.objects.get(pk=serializer.validated_data["warehouse_id"])

        try:
            engine = WarehouseStandardCostEngine(
                formula=formula,
                computed_by=request.user,
                warehouse=warehouse,
            )
            standard_cost = engine.run()
        except (NoOverheadRateError, NoPricedIngredientError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            StandardCostSerializer(standard_cost).data,
            status=status.HTTP_201_CREATED,
        )
