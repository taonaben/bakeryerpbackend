from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin
from apps.costing.models import OverheadRate
from apps.costing.serializers.overhead_rate_serializers import OverheadRateSerializer


class OverheadRateViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """
    Management-only CRUD for OverheadRate records.

    list:   GET  /overhead-rates
    create: POST /overhead-rates
    retrieve: GET /overhead-rates/{id}
    partial_update: PATCH /overhead-rates/{id}
    active: GET /overhead-rates/active?warehouse_id=&date=
    """

    serializer_class = OverheadRateSerializer
    permission_classes = [IsAuthenticated]
    queryset = OverheadRate.objects.select_related("warehouse", "created_by")
    company_field = "warehouse__company"
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        warehouse_id = self.request.query_params.get("warehouse_id")
        period_start = self.request.query_params.get("period_start")
        period_end = self.request.query_params.get("period_end")

        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if period_start:
            qs = qs.filter(period_end__gte=period_start)
        if period_end:
            qs = qs.filter(period_start__lte=period_end)

        return qs.order_by("-period_start")

    def update(self, request, *args, **kwargs):
        # Block updates if CostingEntries already reference this rate
        instance = self.get_object()
        if instance.costing_entries.exists():
            return Response(
                {"detail": "Cannot modify an OverheadRate that has been used in CostingEntries."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        """
        GET /overhead-rates/active?warehouse_id=<uuid>&date=<YYYY-MM-DD>

        Returns the overhead rate active for a given warehouse and date.
        Defaults to today if no date is provided.
        """
        warehouse_id = request.query_params.get("warehouse_id")
        date_str = request.query_params.get("date")

        if not warehouse_id:
            return Response(
                {"detail": "warehouse_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reference_date = (
                timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
                if date_str
                else timezone.now().date()
            )
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rate = (
            OverheadRate.objects.filter(
                warehouse_id=warehouse_id,
                period_start__lte=reference_date,
                period_end__gte=reference_date,
            )
            .order_by("-period_start")
            .first()
        )

        if rate is None:
            return Response(
                {"detail": f"No active OverheadRate found for warehouse {warehouse_id} on {reference_date}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(OverheadRateSerializer(rate).data)
