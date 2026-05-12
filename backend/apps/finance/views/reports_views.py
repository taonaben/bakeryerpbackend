from datetime import date

from drf_spectacular.utils import OpenApiParameter, extend_schema
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

    @extend_schema(
        tags=["Finance - Reports"],
        summary="Get trial balance",
        description=(
            "Returns trial balance totals and account lines for a date range, "
            "optionally scoped to a fiscal period."
        ),
        parameters=[
            OpenApiParameter(
                name="date_from",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Inclusive start date (YYYY-MM-DD).",
            ),
            OpenApiParameter(
                name="date_to",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Inclusive end date (YYYY-MM-DD).",
            ),
            OpenApiParameter(
                name="fiscal_period_id",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Optional fiscal period UUID.",
            ),
        ],
        responses={200: TrialBalanceSerializer},
    )
    def get(self, request):
        today = date.today()
        date_from = _parse_date(
            request.query_params.get("date_from"), date(today.year, 1, 1)
        )
        date_to = _parse_date(request.query_params.get("date_to"), today)
        fiscal_period_id = request.query_params.get("fiscal_period_id")
        data = FinanceReportsService.trial_balance(
            request.user.company, date_from, date_to, fiscal_period_id
        )
        return Response(TrialBalanceSerializer(data).data)


class IncomeStatementView(APIView):
    """GET /finance/reports/income-statement?date_from=&date_to="""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - Reports"],
        summary="Get income statement",
        description="Returns revenue, COGS, expenses, gross profit, and net profit for a date range.",
        parameters=[
            OpenApiParameter(
                name="date_from",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Inclusive start date (YYYY-MM-DD).",
            ),
            OpenApiParameter(
                name="date_to",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Inclusive end date (YYYY-MM-DD).",
            ),
        ],
        responses={200: IncomeStatementSerializer},
    )
    def get(self, request):
        today = date.today()
        date_from = _parse_date(
            request.query_params.get("date_from"), date(today.year, 1, 1)
        )
        date_to = _parse_date(request.query_params.get("date_to"), today)
        data = FinanceReportsService.income_statement(
            request.user.company, date_from, date_to
        )
        return Response(IncomeStatementSerializer(data).data)


class BalanceSheetView(APIView):
    """GET /finance/reports/balance-sheet?as_of_date="""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - Reports"],
        summary="Get balance sheet",
        description="Returns assets, liabilities, equity, and balancing totals as of a date.",
        parameters=[
            OpenApiParameter(
                name="as_of_date",
                type=str,
                location=OpenApiParameter.QUERY,
                description="As-of date for balances (YYYY-MM-DD).",
            ),
        ],
        responses={200: BalanceSheetSerializer},
    )
    def get(self, request):
        as_of_date = _parse_date(request.query_params.get("as_of_date"), date.today())
        data = FinanceReportsService.balance_sheet(request.user.company, as_of_date)
        return Response(BalanceSheetSerializer(data).data)


class ARAgingView(APIView):
    """GET /finance/reports/ar-aging"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - Reports"],
        summary="Get AR aging",
        description="Returns accounts receivable aging buckets by customer.",
        responses={200: ARAgingRowSerializer(many=True)},
    )
    def get(self, request):
        data = FinanceReportsService.ar_aging(request.user.company)
        return Response(ARAgingRowSerializer(data, many=True).data)


class APAgingView(APIView):
    """GET /finance/reports/ap-aging"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - Reports"],
        summary="Get AP aging",
        description="Returns accounts payable aging buckets by supplier.",
        responses={200: APAgingRowSerializer(many=True)},
    )
    def get(self, request):
        data = FinanceReportsService.ap_aging(request.user.company)
        return Response(APAgingRowSerializer(data, many=True).data)
