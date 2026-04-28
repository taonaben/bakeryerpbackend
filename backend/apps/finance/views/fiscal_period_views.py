from django.shortcuts import get_object_or_404
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

    def get(self, request):
        company = request.user.company
        qs = FiscalPeriod.objects.filter(company=company).order_by("period_start")
        period_status = request.query_params.get("status")
        if period_status:
            qs = qs.filter(status=period_status)
        return Response(FiscalPeriodSerializer(qs, many=True).data)

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
        return Response(FiscalPeriodSerializer(period).data, status=status.HTTP_201_CREATED)


class FiscalPeriodDetailView(APIView):
    """GET /finance/fiscal-periods/{id}"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        period = get_object_or_404(FiscalPeriod, pk=pk, company=request.user.company)
        return Response(FiscalPeriodSerializer(period).data)


class FiscalPeriodCloseView(APIView):
    """POST /finance/fiscal-periods/{id}/close"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        period = get_object_or_404(FiscalPeriod, pk=pk, company=request.user.company)
        period = FiscalPeriodService.close_period(period, closed_by=request.user)
        return Response(FiscalPeriodSerializer(period).data)
