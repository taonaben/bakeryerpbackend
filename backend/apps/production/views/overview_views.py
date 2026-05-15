from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.production.serializers import (
    ProductionOverviewSummarySerializer,
    ProductionOverviewWIPSerializer,
    ProductionScheduleAdherenceSerializer,
    ProductionYieldTrendsSerializer,
)
from apps.production.services.overview_service import ProductionOverviewService


class ProductionOverviewBaseView(APIView):
    permission_classes = [IsAuthenticated]

    def _company(self, request):
        return getattr(request.user, "company", None)

    def _bad_request(self, message):
        return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)

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

    def _date_range(self, request):
        return (
            self._parse_date_param(request, "date_from"),
            self._parse_date_param(request, "date_to"),
        )


class ProductionOverviewSummaryView(ProductionOverviewBaseView):
    @extend_schema(
        tags=["Production - Overview"],
        summary="Get production overview summary",
        request=None,
        parameters=[
            OpenApiParameter("date_from", str, required=False),
            OpenApiParameter("date_to", str, required=False),
            OpenApiParameter("warehouse_id", str, required=False),
            OpenApiParameter("limit", int, required=False),
        ],
        responses={200: ProductionOverviewSummarySerializer},
    )
    def get(self, request):
        company = self._company(request)
        if company is None:
            return self._bad_request("Authenticated user is not linked to a company.")

        try:
            date_from, date_to = self._date_range(request)
            limit = self._parse_positive_int(request, "limit", 10)
        except ValueError as exc:
            return self._bad_request(str(exc))

        data = ProductionOverviewService.summary(
            company,
            date_from=date_from,
            date_to=date_to,
            warehouse_id=request.query_params.get("warehouse_id"),
            limit=limit,
        )
        return Response(data)


class ProductionOverviewWIPView(ProductionOverviewBaseView):
    @extend_schema(
        tags=["Production - Overview"],
        summary="Get production work-in-progress overview",
        request=None,
        parameters=[
            OpenApiParameter("warehouse_id", str, required=False),
            OpenApiParameter("limit", int, required=False),
        ],
        responses={200: ProductionOverviewWIPSerializer},
    )
    def get(self, request):
        company = self._company(request)
        if company is None:
            return self._bad_request("Authenticated user is not linked to a company.")

        try:
            limit = self._parse_positive_int(request, "limit", 20)
        except ValueError as exc:
            return self._bad_request(str(exc))

        data = ProductionOverviewService.wip(
            company,
            warehouse_id=request.query_params.get("warehouse_id"),
            limit=limit,
        )
        return Response(data)


class ProductionYieldTrendsView(ProductionOverviewBaseView):
    @extend_schema(
        tags=["Production - Overview"],
        summary="Get production yield trends",
        request=None,
        parameters=[
            OpenApiParameter("date_from", str, required=False),
            OpenApiParameter("date_to", str, required=False),
            OpenApiParameter("warehouse_id", str, required=False),
            OpenApiParameter("interval", str, required=False),
        ],
        responses={200: ProductionYieldTrendsSerializer},
    )
    def get(self, request):
        company = self._company(request)
        if company is None:
            return self._bad_request("Authenticated user is not linked to a company.")

        interval = request.query_params.get("interval", "month")
        if interval not in ("day", "week", "month"):
            return self._bad_request("interval must be one of: day, week, month.")

        try:
            date_from, date_to = self._date_range(request)
        except ValueError as exc:
            return self._bad_request(str(exc))

        data = ProductionOverviewService.yield_trends(
            company,
            date_from=date_from,
            date_to=date_to,
            warehouse_id=request.query_params.get("warehouse_id"),
            interval=interval,
        )
        return Response(data)


class ProductionScheduleAdherenceView(ProductionOverviewBaseView):
    @extend_schema(
        tags=["Production - Overview"],
        summary="Get approximate production schedule adherence",
        request=None,
        parameters=[
            OpenApiParameter("date_from", str, required=False),
            OpenApiParameter("date_to", str, required=False),
            OpenApiParameter("warehouse_id", str, required=False),
            OpenApiParameter("limit", int, required=False),
        ],
        responses={200: ProductionScheduleAdherenceSerializer},
    )
    def get(self, request):
        company = self._company(request)
        if company is None:
            return self._bad_request("Authenticated user is not linked to a company.")

        try:
            date_from, date_to = self._date_range(request)
            limit = self._parse_positive_int(request, "limit", 20)
        except ValueError as exc:
            return self._bad_request(str(exc))

        data = ProductionOverviewService.schedule_adherence(
            company,
            date_from=date_from,
            date_to=date_to,
            warehouse_id=request.query_params.get("warehouse_id"),
            limit=limit,
        )
        return Response(data)
