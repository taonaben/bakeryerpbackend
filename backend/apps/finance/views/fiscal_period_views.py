from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import FiscalPeriod
from apps.finance.serializers.fiscal_period_serializers import (
    FiscalPeriodCreateSerializer,
    FiscalPeriodSerializer,
)
from apps.finance.services.fiscal_period_service import FiscalPeriodService


class FiscalPeriodListView(APIView):
    """
    GET  /finance/fiscal-periods        list (filter by status)
    POST /finance/fiscal-periods        create
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - Fiscal Periods"],
        summary="List fiscal periods",
        description="Returns fiscal periods for the current company.",
        parameters=[
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by period status.",
                enum=["open", "closed"],
            ),
        ],
        responses={200: FiscalPeriodSerializer(many=True)},
    )
    def get(self, request):
        company = request.user.company
        qs = FiscalPeriod.objects.filter(company=company).order_by("period_start")
        period_status = request.query_params.get("status")
        if period_status:
            qs = qs.filter(status=period_status)
        return Response(FiscalPeriodSerializer(qs, many=True).data)

    @extend_schema(
        tags=["Finance - Fiscal Periods"],
        summary="Create fiscal period",
        description="Creates a new open fiscal period for the current company.",
        request=FiscalPeriodCreateSerializer,
        responses={201: FiscalPeriodSerializer},
    )
    def post(self, request):
        serializer = FiscalPeriodCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        period = FiscalPeriodService.create_period(
            company=request.user.company,
            name=d["name"],
            period_start=d["period_start"],
            period_end=d["period_end"],
        )
        return Response(
            FiscalPeriodSerializer(period).data, status=status.HTTP_201_CREATED
        )


class FiscalPeriodDetailView(APIView):
    """GET /finance/fiscal-periods/{id}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - Fiscal Periods"],
        summary="Get fiscal period",
        description="Returns a single fiscal period by id.",
        responses={200: FiscalPeriodSerializer},
    )
    def get(self, request, pk):
        period = get_object_or_404(FiscalPeriod, pk=pk, company=request.user.company)
        return Response(FiscalPeriodSerializer(period).data)


class FiscalPeriodCloseView(APIView):
    """POST /finance/fiscal-periods/{id}/close"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - Fiscal Periods"],
        summary="Close fiscal period",
        description="Closes an open fiscal period and stamps close metadata.",
        request=None,
        responses={200: FiscalPeriodSerializer},
    )
    def post(self, request, pk):
        period = get_object_or_404(FiscalPeriod, pk=pk, company=request.user.company)
        period = FiscalPeriodService.close_period(period, closed_by=request.user)
        return Response(FiscalPeriodSerializer(period).data)
