from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.sales.models import Customer
from apps.sales.serializers.reports_serializers import (
    CustomerStatementSerializer,
    DailySummarySerializer,
    MarginByProductSerializer,
    OutstandingDebtorSerializer,
    RevenueByProductSerializer,
    SalesByWarehouseSerializer,
)
from apps.sales.services.reports_services import ReportsService


def _parse_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


class DailySummaryView(APIView):
    """GET /reports/daily-summary?date=YYYY-MM-DD&warehouse_id="""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        report_date = _parse_date(request.query_params.get("date"), date.today())
        warehouse_id = request.query_params.get("warehouse_id")
        data = ReportsService.daily_summary(report_date, warehouse_id)
        return Response(DailySummarySerializer(data).data)


class RevenueByProductView(APIView):
    """GET /reports/revenue-by-product?date_from=&date_to=&warehouse_id="""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = date.today()
        date_from = _parse_date(request.query_params.get("date_from"), date(today.year, today.month, 1))
        date_to = _parse_date(request.query_params.get("date_to"), today)
        warehouse_id = request.query_params.get("warehouse_id")
        data = ReportsService.revenue_by_product(date_from, date_to, warehouse_id)
        return Response(RevenueByProductSerializer(data, many=True).data)


class MarginByProductView(APIView):
    """GET /reports/margin-by-product?date_from=&date_to=&warehouse_id="""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = date.today()
        date_from = _parse_date(request.query_params.get("date_from"), date(today.year, today.month, 1))
        date_to = _parse_date(request.query_params.get("date_to"), today)
        warehouse_id = request.query_params.get("warehouse_id")
        data = ReportsService.margin_by_product(date_from, date_to, warehouse_id)
        return Response(MarginByProductSerializer(data, many=True).data)


class CustomerStatementView(APIView):
    """GET /reports/customer-statement/{id}"""
    permission_classes = [IsAuthenticated]

    def get(self, request, customer_id):
        get_object_or_404(Customer, pk=customer_id)
        data = ReportsService.customer_statement(customer_id)
        return Response(CustomerStatementSerializer(data).data)


class OutstandingDebtorsView(APIView):
    """GET /reports/outstanding-debtors"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = ReportsService.outstanding_debtors()
        return Response(OutstandingDebtorSerializer(data, many=True).data)


class SalesByWarehouseView(APIView):
    """GET /reports/sales-by-warehouse?date_from=&date_to="""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = date.today()
        date_from = _parse_date(request.query_params.get("date_from"), date(today.year, today.month, 1))
        date_to = _parse_date(request.query_params.get("date_to"), today)
        data = ReportsService.sales_by_warehouse(date_from, date_to)
        return Response(SalesByWarehouseSerializer(data, many=True).data)
