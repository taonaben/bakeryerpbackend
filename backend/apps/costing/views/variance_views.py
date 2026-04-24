from django.db.models import Avg, Count, Q, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin
from apps.costing.models import CostVarianceRecord
from apps.costing.serializers.variance_serializers import (
    CostVarianceRecordSerializer,
    VarianceSummarySerializer,
)


class CostVarianceViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    """
    Read-only access to CostVarianceRecord.

    list:    GET /variances
    retrieve: GET /variances/{id}
    summary: GET /variances/summary?group_by=product|warehouse&date_from=&date_to=
    """

    serializer_class = CostVarianceRecordSerializer
    permission_classes = [IsAuthenticated]
    queryset = CostVarianceRecord.objects.select_related(
        "product", "warehouse", "production_batch", "standard_cost", "costing_entry"
    )
    company_field = "product__company"

    def get_queryset(self):
        qs = super().get_queryset()
        product_id = self.request.query_params.get("product_id")
        warehouse_id = self.request.query_params.get("warehouse_id")
        is_favourable = self.request.query_params.get("is_favourable")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if product_id:
            qs = qs.filter(product_id=product_id)
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if is_favourable is not None:
            qs = qs.filter(is_favourable=is_favourable.lower() == "true")
        if date_from:
            qs = qs.filter(computed_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(computed_at__date__lte=date_to)

        return qs.order_by("-computed_at")

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """
        GET /variances/summary?group_by=product&date_from=2026-01-01&date_to=2026-03-31

        Aggregates variance data by product or warehouse for a period.
        group_by: "product" (default) | "warehouse"
        """
        group_by = request.query_params.get("group_by", "product")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        qs = self.get_queryset()
        if date_from:
            qs = qs.filter(computed_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(computed_at__date__lte=date_to)

        if group_by == "warehouse":
            group_field = "warehouse_id"
            name_field = "warehouse__name"
        else:
            group_field = "product_id"
            name_field = "product__name"

        rows = (
            qs.values(group_field, name_field)
            .annotate(
                total_variance=Sum("total_variance"),
                avg_variance_percentage=Avg("variance_percentage"),
                favourable_count=Count("id", filter=Q(is_favourable=True)),
                adverse_count=Count("id", filter=Q(is_favourable=False)),
                batch_count=Count("id"),
            )
            .order_by("total_variance")  # worst performers first
        )

        results = [
            {
                "group_by": group_by,
                "group_id": row[group_field],
                "group_name": row[name_field],
                "total_variance": row["total_variance"],
                "avg_variance_percentage": row["avg_variance_percentage"],
                "favourable_count": row["favourable_count"],
                "adverse_count": row["adverse_count"],
                "batch_count": row["batch_count"],
            }
            for row in rows
        ]

        return Response(VarianceSummarySerializer(results, many=True).data)
