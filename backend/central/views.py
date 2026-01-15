from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Company, Warehouse, Product
from .serializers import CompanySerializer, WarehouseSerializer, ProductSerializer


class CompanyViewSet(viewsets.ModelViewSet):
    """ViewSet for Company CRUD operations"""

    queryset = Company.objects.all()
    serializer_class = CompanySerializer

    @action(detail=True, methods=["get"])
    def warehouses(self, request, pk=None):
        """Get all warehouses for a company"""
        company = self.get_object()
        warehouses = company.warehouses.all()
        serializer = WarehouseSerializer(warehouses, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get all active companies"""
        companies = Company.objects.filter(status=True)
        serializer = self.get_serializer(companies, many=True)
        return Response(serializer.data)


class WarehouseViewSet(viewsets.ModelViewSet):
    """ViewSet for Warehouse CRUD operations"""

    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer

    def get_queryset(self):
        """Filter warehouses by company if provided"""
        queryset = Warehouse.objects.all()
        company_id = self.request.query_params.get("company_id", None)
        if company_id is not None:
            queryset = queryset.filter(company_id=company_id)
        return queryset

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get all active warehouses"""
        warehouses = Warehouse.objects.filter(status=True)
        serializer = self.get_serializer(warehouses, many=True)
        return Response(serializer.data)


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for Product CRUD operations"""

    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def get_queryset(self):
        """Filter products by category if provided"""
        queryset = Product.objects.all()
        category = self.request.query_params.get("category", None)
        if category is not None:
            queryset = queryset.filter(category=category)
        return queryset

    @action(detail=False, methods=["get"])
    def by_category(self, request):
        """Get all unique product categories"""
        categories = Product.objects.values_list("category", flat=True).distinct()
        return Response({"categories": list(categories)})

    @action(detail=True, methods=["get"])
    def by_sku(self, request, pk=None):
        """Get product by SKU"""
        try:
            product = Product.objects.get(sku=pk)
            serializer = self.get_serializer(product)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product with this SKU not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
