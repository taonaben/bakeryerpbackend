from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin
from apps.costing.models import CostingEntry, CostingEntryLine
from apps.costing.serializers.costing_entry_serializers import (
    ComputeCostingEntrySerializer,
    CostingEntryLineSerializer,
    CostingEntryListSerializer,
    CostingEntrySerializer,
)


class CostingEntryViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    """
    Read-only access to CostingEntry records.
    Write access is exclusively via the compute action.

    list:     GET /costing-entries
    retrieve: GET /costing-entries/{id}
    lines:    GET /costing-entries/{id}/lines
    variance: GET /costing-entries/{id}/variance
    compute:  POST /costing-entries/compute
    """

    permission_classes = [IsAuthenticated]
    queryset = CostingEntry.objects.select_related(
        "production_batch", "product", "warehouse", "standard_cost", "overhead_rate"
    ).prefetch_related("lines", "lines__product")
    company_field = "product__company"

    def get_serializer_class(self):
        if self.action == "list":
            return CostingEntryListSerializer
        return CostingEntrySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        product_id = self.request.query_params.get("product_id")
        warehouse_id = self.request.query_params.get("warehouse_id")
        batch_id = self.request.query_params.get("batch_id")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if product_id:
            qs = qs.filter(product_id=product_id)
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if batch_id:
            qs = qs.filter(production_batch_id=batch_id)
        if date_from:
            qs = qs.filter(computed_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(computed_at__date__lte=date_to)

        return qs.order_by("-computed_at")

    @action(detail=True, methods=["get"], url_path="lines")
    def lines(self, request, pk=None):
        """GET /costing-entries/{id}/lines — ingredient-level actual breakdown."""
        entry = self.get_object()
        lines = CostingEntryLine.objects.filter(
            costing_entry=entry
        ).select_related("product", "batch_material")
        return Response(CostingEntryLineSerializer(lines, many=True).data)

    @action(detail=True, methods=["get"], url_path="variance")
    def variance(self, request, pk=None):
        """GET /costing-entries/{id}/variance — the variance record for this entry."""
        from apps.costing.serializers.variance_serializers import CostVarianceRecordSerializer

        entry = self.get_object()
        if not hasattr(entry, "variance_record"):
            return Response(
                {"detail": "No variance record found for this costing entry. It may still be pending."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(CostVarianceRecordSerializer(entry.variance_record).data)

    @action(detail=False, methods=["post"], url_path="compute")
    def compute(self, request):
        """
        POST /costing-entries/compute
        Body: { "production_batch_id": "<uuid>", "force": false }

        Runs CostingEngine. Blocks if entry already exists unless force=true.
        With force=true, logs an audit warning but proceeds.
        """
        serializer = ComputeCostingEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.production.models import ProductionBatch
        from apps.costing.services.costing_engine import CostingEngine, CostingEngineError

        batch = ProductionBatch.objects.get(
            pk=serializer.validated_data["production_batch_id"]
        )
        force = serializer.validated_data.get("force", False)

        # Guard: block if already costed and force not set
        if hasattr(batch, "costing_entry") and not force:
            return Response(
                {
                    "detail": "A CostingEntry already exists for this batch. "
                              "Pass force=true to create an amended entry.",
                    "existing_entry_id": str(batch.costing_entry.id),
                },
                status=status.HTTP_409_CONFLICT,
            )

        if batch.status != "completed":
            return Response(
                {"detail": "Cannot cost a batch that is not in 'completed' status."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            engine = CostingEngine(production_batch=batch)
            entry = engine.run()
        except CostingEngineError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response(
            CostingEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )
