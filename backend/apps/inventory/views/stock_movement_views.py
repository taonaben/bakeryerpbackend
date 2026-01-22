from django.shortcuts import render
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from ..models import Stock, StockMovement, Batch
from drf_spectacular.utils import extend_schema, OpenApiParameter
from ..filters import StockFilter, StockMovementFilter, BatchFilter
from ..serializers import StockSerializer, StockMovementSerializer, BatchSerializer
from .utils import CustomPagination, InventoryPermission, filter_backends


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

    serializer_class = StockMovementSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated, InventoryPermission]
    filterset_class = StockMovementFilter
    filter_backends = filter_backends
    ordering_fields = ["created_at", "quantity"]
    search_fields = ["reference_number", "notes"]
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
