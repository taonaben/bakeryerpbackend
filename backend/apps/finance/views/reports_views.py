from datetime import date

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.serializers.reports_serilizers import (
    APAgingRowSerializer,
    ARAgingRowSerializer,
    BalanceSheetSerializer,
    IncomeStatementSerializer,
    TrialBalanceSerializer,
)
from apps.finance.services.reports_service import FinanceReportsService


def _parse_date(value, default: date) -> date:
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


class TrialBalanceView(APIView):
    """GET /finance/reports/trial-balance?date_from=&date_to=&fiscal_period_id="""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = date.today()
        date_from = _parse_date(request.query_params.get("date_from"), date(today.year, 1, 1))
        date_to = _parse_date(request.query_params.get("date_to"), today)
        fiscal_period_id = request.query_params.get("fiscal_period_id")
        data = FinanceReportsService.trial_balance(
            request.user.company, date_from, date_to, fiscal_period_id
        )
        return Response(TrialBalanceSerializer(data).data)


class IncomeStatementView(APIView):
    """GET /finance/reports/income-statement?date_from=&date_to="""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = date.today()
        date_from = _parse_date(request.query_params.get("date_from"), date(today.year, 1, 1))
        date_to = _parse_date(request.query_params.get("date_to"), today)
        data = FinanceReportsService.income_statement(request.user.company, date_from, date_to)
        return Response(IncomeStatementSerializer(data).data)


class BalanceSheetView(APIView):
    """GET /finance/reports/balance-sheet?as_of_date="""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        as_of_date = _parse_date(request.query_params.get("as_of_date"), date.today())
        data = FinanceReportsService.balance_sheet(request.user.company, as_of_date)
        return Response(BalanceSheetSerializer(data).data)


class ARAgingView(APIView):
    """GET /finance/reports/ar-aging"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = FinanceReportsService.ar_aging(request.user.company)
        return Response(ARAgingRowSerializer(data, many=True).data)


class APAgingView(APIView):
    """GET /finance/reports/ap-aging"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = FinanceReportsService.ap_aging(request.user.company)
        return Response(APAgingRowSerializer(data, many=True).data)
