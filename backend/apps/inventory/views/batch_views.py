from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin
from ..models import Batch, StockMovement
from drf_spectacular.utils import extend_schema, OpenApiParameter
from ..filters import BatchFilter
from ..serializers import BatchSerializer, StockMovementSerializer
from .utils import CustomPagination, InventoryPermission, filter_backends


class BatchViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing batches of products in inventory's warehouses.

    Allows filtering by product or warehouse.

    Query parameters:\n
        - product_id: Filter batches by product ID\n
        - warehouse_id: Filter batches by warehouse ID
    """

    queryset = Batch.objects.all()
    company_field = "warehouse__company"
    serializer_class = BatchSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated, InventoryPermission]
    filterset_class = BatchFilter
    filter_backends = filter_backends
    ordering_fields = [
        "created_at",
        "product__name",
        "batch_number",
        "manufacture_date",
        "expiry_date",
        "quantity",
    ]
    search_fields = ["product__name", "batch_number"]
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

    @action(
        detail=True,
        methods=["get"],
        permission_classes=[IsAuthenticated, InventoryPermission],
        pagination_class=CustomPagination,
    )
    @extend_schema(
        summary="Get movements for a batch",
        description="Retrieve all stock movements associated with a specific batch to track its movement history.",
        tags=["Batches"],
    )
    def movements(self, request, pk=None):
        """
        Get all movements associated with this batch.

        Returns paginated list of stock movements with batch-specific details.
        """
        batch = self.get_object()
        movements = batch.movements.all().order_by("-created_at")

        page = self.paginate_queryset(movements)
        if page is not None:
            serializer = StockMovementSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)
