from django.shortcuts import render
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from ..models import InventoryAlert, ProductPolicy
from drf_spectacular.utils import extend_schema, OpenApiParameter
from ..filters import StockFilter, StockMovementFilter, BatchFilter
from ..serializers import InventoryAlertSerializer, ProductReorderPolicySerializer
from .utils import CustomPagination, InventoryPermission, filter_backends


class InventoryAlertViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing inventory alerts.

    Read-only access to inventory alerts.
    """

    serializer_class = InventoryAlertSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated, InventoryPermission]
    filter_backends = filter_backends
    ordering_fields = ["created_at", "alert_type", "status"]
    search_fields = ["product__name", "product__sku"]
    tags = ["Inventory Alerts"]

    def get_queryset(self):
        """Filter inventory alerts by warehouse if provided"""
        queryset = InventoryAlert.objects.select_related(
            "product", "warehouse", "reorder_policy"
        ).all()
        warehouse_id = self.request.query_params.get("warehouse_id")

        if warehouse_id is not None:
            try:
                warehouse_id = warehouse_id.strip()
                queryset = queryset.filter(warehouse_id=warehouse_id)
            except (ValueError, TypeError):
                queryset = queryset.none()

        return queryset

    @action(detail=False, methods=["get"])
    def low_stock(self, request):
        """Retrieve all low stock alerts"""
        alerts = InventoryAlert.objects.filter(alert_type="LOW_STOCK")
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def out_of_stock(self, request):
        """Retrieve all out of stock alerts"""
        alerts = InventoryAlert.objects.filter(alert_type="OUT_OF_STOCK")
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def expiry(self, request):
        """Retrieve all expiry alerts"""
        alerts = InventoryAlert.objects.filter(alert_type="EXPIRY")
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def open(self, request):
        """Retrieve all open alerts"""
        alerts = InventoryAlert.objects.filter(status="OPEN")
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def acknowledged(self, request):
        """Retrieve all acknowledged alerts"""
        alerts = InventoryAlert.objects.filter(status="ACKNOWLEDGED")
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["patch"])
    def acknowledge(self, request, pk=None):
        """Acknowledge an alert"""
        alert = self.get_object()
        if alert.status == "OPEN":
            alert.status = "ACKNOWLEDGED"
            alert.acknowledged_at = timezone.now()
            alert.acknowledged_by = request.user
            alert.save()
            return Response({"status": "Alert acknowledged"})
        return Response(
            {"error": "Alert is not in OPEN status"}, status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=["patch"])
    def resolve(self, request, pk=None):
        """Resolve an alert"""
        alert = self.get_object()
        if alert.status in ["OPEN", "ACKNOWLEDGED"]:
            alert.status = "RESOLVED"
            alert.resolved_at = timezone.now()
            alert.resolved_by = request.user
            alert.save()
            return Response({"status": "Alert resolved"})
        return Response(
            {"error": "Alert cannot be resolved"}, status=status.HTTP_400_BAD_REQUEST
        )


class ProductReorderPolicyViewSet(viewsets.ModelViewSet):
    """
    Docstring for ProductReorderPolicyViewSet

    ViewSet for managing product reorder policies.
    """

    queryset = ProductPolicy.objects.all()
    serializer_class = ProductReorderPolicySerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated, InventoryPermission]
    filter_backends = filter_backends
    ordering_fields = ["created_at", "product__name"]
    search_fields = ["product__name", "product__sku"]
    tags = ["Product Reorder Policies"]
