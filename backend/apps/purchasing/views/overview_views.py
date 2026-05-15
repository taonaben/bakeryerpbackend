from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.purchasing.serializers.overview_serializers import (
    PurchasingOverviewSummarySerializer,
    PurchasingOverviewTrendsSerializer,
    PurchasingSupplierPerformanceSerializer,
)
from apps.purchasing.services.overview_service import PurchasingOverviewService


class PurchasingOverviewBaseView(APIView):
    permission_classes = [IsAuthenticated]

    def _company(self, request):
        company = getattr(request.user, "company", None)
        if company is None:
            return None
        return company

    def _parse_date_param(self, request, name):
        value = request.query_params.get(name)
        if not value:
            return None
        parsed = parse_date(value)
        if parsed is None:
            raise ValueError(f"{name} must be a valid date in YYYY-MM-DD format.")
        return parsed

    def _parse_positive_int(self, request, name, default):
        value = request.query_params.get(name)
        if value in (None, ""):
            return default
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a positive integer.")
        if parsed <= 0:
            raise ValueError(f"{name} must be a positive integer.")
        return parsed

    def _bad_request(self, message):
        return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)


class PurchasingOverviewSummaryView(PurchasingOverviewBaseView):
    @extend_schema(
        tags=["Purchasing - Overview"],
        summary="Get purchasing overview summary",
        request=None,
        parameters=[
            OpenApiParameter("warehouse_id", str, required=False),
            OpenApiParameter("expiring_within_days", int, required=False),
        ],
        responses={200: PurchasingOverviewSummarySerializer},
    )
    def get(self, request):
        company = self._company(request)
        if company is None:
            return self._bad_request("Authenticated user is not linked to a company.")

        try:
            expiring_within_days = self._parse_positive_int(
                request, "expiring_within_days", 30
            )
        except ValueError as exc:
            return self._bad_request(str(exc))

        data = PurchasingOverviewService.summary(
            company,
            warehouse_id=request.query_params.get("warehouse_id"),
            expiring_within_days=expiring_within_days,
        )
        return Response(data)


class PurchasingOverviewTrendsView(PurchasingOverviewBaseView):
    @extend_schema(
        tags=["Purchasing - Overview"],
        summary="Get purchasing overview trends",
        request=None,
        parameters=[
            OpenApiParameter("date_from", str, required=False),
            OpenApiParameter("date_to", str, required=False),
            OpenApiParameter("warehouse_id", str, required=False),
            OpenApiParameter("interval", str, required=False),
        ],
        responses={200: PurchasingOverviewTrendsSerializer},
    )
    def get(self, request):
        company = self._company(request)
        if company is None:
            return self._bad_request("Authenticated user is not linked to a company.")

        interval = request.query_params.get("interval", "month")
        if interval not in ("day", "week", "month"):
            return self._bad_request("interval must be one of: day, week, month.")

        try:
            date_from = self._parse_date_param(request, "date_from")
            date_to = self._parse_date_param(request, "date_to")
        except ValueError as exc:
            return self._bad_request(str(exc))

        data = PurchasingOverviewService.trends(
            company,
            date_from=date_from,
            date_to=date_to,
            warehouse_id=request.query_params.get("warehouse_id"),
            interval=interval,
        )
        return Response(data)


class PurchasingSupplierPerformanceView(PurchasingOverviewBaseView):
    @extend_schema(
        tags=["Purchasing - Overview"],
        summary="Get supplier performance overview",
        request=None,
        parameters=[
            OpenApiParameter("date_from", str, required=False),
            OpenApiParameter("date_to", str, required=False),
            OpenApiParameter("supplier_id", str, required=False),
            OpenApiParameter("limit", int, required=False),
        ],
        responses={200: PurchasingSupplierPerformanceSerializer},
    )
    def get(self, request):
        company = self._company(request)
        if company is None:
            return self._bad_request("Authenticated user is not linked to a company.")

        try:
            date_from = self._parse_date_param(request, "date_from")
            date_to = self._parse_date_param(request, "date_to")
            limit = self._parse_positive_int(request, "limit", 10)
        except ValueError as exc:
            return self._bad_request(str(exc))

        data = PurchasingOverviewService.supplier_performance(
            company,
            date_from=date_from,
            date_to=date_to,
            supplier_id=request.query_params.get("supplier_id"),
            limit=limit,
        )
        return Response(data)
