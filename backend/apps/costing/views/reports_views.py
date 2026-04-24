from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.costing.services.reports_service import CostingReportsService


class CostTrendView(APIView):
    """
    GET /reports/cost-trend/{product_id}?warehouse_id=&limit=20

    Cost per unit over time for a product across completed batches.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, product_id):
        warehouse_id = request.query_params.get("warehouse_id")
        limit = int(request.query_params.get("limit", 20))
        data = CostingReportsService.cost_trend(
            product_id=product_id,
            warehouse_id=warehouse_id,
            limit=limit,
        )
        return Response(data)


class VarianceAnalysisView(APIView):
    """
    GET /reports/variance-analysis?product_id=&warehouse_id=&date_from=&date_to=

    Aggregated variance breakdown by product and warehouse.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = CostingReportsService.variance_analysis(
            product_id=request.query_params.get("product_id"),
            warehouse_id=request.query_params.get("warehouse_id"),
            date_from=request.query_params.get("date_from"),
            date_to=request.query_params.get("date_to"),
        )
        return Response(data)


class MarginReportView(APIView):
    """
    GET /reports/margin-report?product_id=

    Gross margin per product using latest cost + pricing rule.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = CostingReportsService.margin_report(
            product_id=request.query_params.get("product_id"),
        )
        return Response(data)


class IngredientCostBreakdownView(APIView):
    """
    GET /reports/ingredient-cost-breakdown?product_id=&formula_id=

    Ingredient cost ranking from the latest StandardCost for a product or formula.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = CostingReportsService.ingredient_cost_breakdown(
            product_id=request.query_params.get("product_id"),
            formula_id=request.query_params.get("formula_id"),
        )
        return Response(data)
