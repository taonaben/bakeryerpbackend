from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin
from ..models import StockMovement
from ..filters import StockMovementFilter
from ..serializers import StockMovementSerializer
from ..services.stock_movement_service import (
    create_stock_movement,
    repair_missing_movement_batches,
)
from .utils import CustomPagination, InventoryPermission, filter_backends


class StockMovementViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
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
    ordering_fields = ["created_at", "total_quantity", "movement_type"]
    search_fields = ["reference_number", "notes"]
    tags = ["Stock Movements"]

    company_field = "batches__warehouse__company"
    
    def get_queryset(self):
        """Filter stock movements by warehouse and date range if provided"""
        queryset = StockMovement.objects.all()
        warehouse_id = self.request.query_params.get("warehouse_id")
        start_date = self.request.query_params.get("start_date", None)
        end_date = self.request.query_params.get("end_date", None)

        if warehouse_id is not None:
            queryset = queryset.filter(batches__warehouse_id=warehouse_id).distinct()

        if start_date is not None and end_date is not None:
            queryset = queryset.filter(created_at__range=[start_date, end_date])

        return queryset.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        movement = create_stock_movement(
            request.data,
            serializer_class=self.get_serializer_class(),
            context=self.get_serializer_context(),
        )
        response_serializer = self.get_serializer(movement)
        headers = self.get_success_headers(response_serializer.data)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    @action(detail=False, methods=["get"])
    def by_stock(self, request):
        """Retrieve stock movements for a specific stock item"""
        stock_id = request.query_params.get("stock_id", None)
        if stock_id is not None:
            movements = StockMovement.objects.filter(
                batches__product__stocks__id=stock_id
            ).distinct()
            serializer = self.get_serializer(movements, many=True)
            return Response(serializer.data)
        return Response(
            {"detail": "stock_id parameter is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=["post"], url_path="repair-missing-batches")
    def repair_missing_batches(self, request):
        result = repair_missing_movement_batches(request.data)
        return Response(result, status=status.HTTP_200_OK)
