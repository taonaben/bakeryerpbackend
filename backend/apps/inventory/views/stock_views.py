from django.shortcuts import render
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin
from ..models import Stock, StockMovement, Batch
from drf_spectacular.utils import extend_schema, OpenApiParameter
from ..filters import StockFilter, StockMovementFilter, BatchFilter
from ..serializers import StockSerializer, StockMovementSerializer, BatchSerializer
from .utils import CustomPagination, InventoryPermission, filter_backends


class StockViewSet(CompanyScopedMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing stock levels of products in warehouses.

    Read-only access to current inventory levels.

    Query parameters:\n
        - warehouse_id: Filter stocks by warehouse ID\n
    Custom actions:\n
        - by_product_sku: Get stock for specific product SKU (requires 'sku' parameter)
    """

    queryset = Stock.objects.all().order_by("-created_at")
    serializer_class = StockSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated, InventoryPermission]
    filterset_class = StockFilter
    filter_backends = filter_backends
    ordering_fields = [
        "quantity_on_hand",
        "status",
        "created_at",
        "product__name",
        "last_updated",
    ]
    search_fields = ["product__name", "product__sku"]
    tags = ["Stocks"]
    
    company_field = "product__company"

    @action(detail=False, methods=["get"])
    def by_product_sku(self, request):
        """Retrieve stock items for a specific product SKU"""
        sku = request.query_params.get("sku", None)
        if sku is not None:
            stocks = Stock.objects.filter(product__sku=sku).order_by("-last_updated")
            serializer = self.get_serializer(stocks, many=True)
            return Response(serializer.data)
        return Response(
            {"detail": "sku parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
