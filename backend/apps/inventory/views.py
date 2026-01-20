from django.shortcuts import render
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Stock, StockMovement, Batch
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .filters import StockFilter, StockMovementFilter, BatchFilter
from apps.accounts.permissions import ModulePermission

from .serializers import StockSerializer, StockMovementSerializer, BatchSerializer

# Create your views here.


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class InventoryPermission(ModulePermission):
    module = "inventory"


class StockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing stock levels of products in warehouses.

    Read-only access to current inventory levels.

    Query parameters:\n
        - warehouse_id: Filter stocks by warehouse ID\n
    Custom actions:\n
        - by_product_sku: Get stock for specific product SKU (requires 'sku' parameter)
    """

    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated, InventoryPermission]
    filterset_class = StockFilter
    tags = ["Stocks"]

    @action(detail=False, methods=["get"])
    def by_product_sku(self, request):
        """Retrieve stock items for a specific product SKU"""
        sku = request.query_params.get("sku", None)
        if sku is not None:
            stocks = Stock.objects.filter(product__sku=sku)
            serializer = self.get_serializer(stocks, many=True)
            return Response(serializer.data)
        return Response(
            {"detail": "sku parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class BatchViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing batches of products in inventory's warehouses.

    Allows filtering by product or warehouse.

    Query parameters:\n
        - product_id: Filter batches by product ID\n
        - warehouse_id: Filter batches by warehouse ID
    """

    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated, InventoryPermission]
    filterset_class = BatchFilter
    tags = ["Batches"]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="product_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter batches by product ID",
            ),
            OpenApiParameter(
                name="warehouse_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter batches by warehouse ID",
            ),
        ]
    )
    def get_queryset(self):
        """Filter batches by product or warehouse if provided"""
        queryset = Batch.objects.all()
        product_id = self.request.query_params.get("product_id", None)
        warehouse_id = self.request.query_params.get("warehouse_id", None)

        if product_id is not None:
            queryset = queryset.filter(product_id=product_id)
        if warehouse_id is not None:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        return queryset


class StockMovementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing stock movements and inventory transactions.

    Supports creating, viewing, updating, and deleting stock movements.

    Query parameters:\n
        - warehouse_id: Filter movements by warehouse ID\n
        - start_date: Filter movements from this date (YYYY-MM-DD)\n
        - end_date: Filter movements until this date (YYYY-MM-DD)\n
    Custom actions:\n
        - by_stock: Get movements for specific stock item (requires 'stock_id' parameter)
    """

    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated, InventoryPermission]
    filterset_class = StockMovementFilter
    tags = ["Stock Movements"]

    def get_queryset(self):
        """Filter stock movements by warehouse and date range if provided"""
        queryset = StockMovement.objects.all()
        warehouse_id = self.request.query_params.get("warehouse_id")
        start_date = self.request.query_params.get("start_date", None)
        end_date = self.request.query_params.get("end_date", None)

        if warehouse_id is not None:
            queryset = queryset.filter(batch__warehouse_id=warehouse_id)

        if start_date is not None and end_date is not None:
            queryset = queryset.filter(created_at__range=[start_date, end_date])

        return queryset

    @action(detail=False, methods=["get"])
    def by_stock(self, request):
        """Retrieve stock movements for a specific stock item"""
        stock_id = request.query_params.get("stock_id", None)
        if stock_id is not None:
            movements = StockMovement.objects.filter(stock_id=stock_id)
            serializer = self.get_serializer(movements, many=True)
            return Response(serializer.data)
        return Response(
            {"detail": "stock_id parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
