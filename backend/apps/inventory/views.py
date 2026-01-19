from django.shortcuts import render
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Stock, StockMovement, Batch

from .serializers import StockSerializer, StockMovementSerializer, BatchSerializer

# Create your views here.


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class StockViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]
    tags = ["Stocks"]

    def get_queryset(self):
        """Filter stocks by warehouse if provided"""
        queryset = Stock.objects.all()
        warehouse_id = self.request.query_params.get("warehouse_id", None)
        if warehouse_id is not None:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        return queryset


class BatchViewSet(viewsets.ModelViewSet):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]
    tags = ["Batches"]

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
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]
    tags = ["Stock Movements"]

    def get_queryset(self):
        """Filter stock movements by date range if provided"""
        queryset = StockMovement.objects.all()
        start_date = self.request.query_params.get("start_date", None)
        end_date = self.request.query_params.get("end_date", None)
        if start_date is not None and end_date is not None:
            queryset = queryset.filter(date__range=[start_date, end_date])
        return queryset

    def create(self, request, *args, **kwargs):
        """Create a new stock movement"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch_id = self.request.query_params.get("batch_id", None)
        if batch_id is not None:
            serializer.save(batch_id=batch_id)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
