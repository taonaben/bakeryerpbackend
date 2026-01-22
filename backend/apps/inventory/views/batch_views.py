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
    filter_backends = filter_backends
    ordering_fields = ["created_at", "product__name"]
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
