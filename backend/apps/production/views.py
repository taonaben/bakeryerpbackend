from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework import viewsets, status, generics

from .models import ProductionOrder
from apps.inventory.serializers import StockMovementSerializer

from .serializers import (
    ProductionOrderSerializer,
    ProductionPlanSerializer,
    StartProductionSerializer,
    ProductionBatchSerializer,
)
from .services.production_planner import ProductionPlanner
from .services.production_engine import ProductionEngine


class ProductionPlanAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        order = get_object_or_404(ProductionOrder, id=order_id)

        try:
            plan = ProductionPlanner.plan(order)
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProductionPlanSerializer(plan)
        return Response(serializer.data)


class ProductionOrderViewSet(viewsets.ModelViewSet):
    serializer_class = ProductionOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get Production orders in Warehouse and optionally filter by status & product"""

        queryset = ProductionOrder.objects.all()
        warehouse_id = self.request.query_params.get("warehouse_id")
        status = self.request.query_params.get("status")
        product_id = self.request.query_params.get("product_id")

        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if status:
            queryset = queryset.filter(status=status)
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        return queryset


class ProductionStartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        serializer = StartProductionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = ProductionEngine.start_production(
                order_id=order_id,
                quantity=serializer.validated_data.get("quantity"),
                selected_batches=serializer.validated_data.get("selected_batches"),
            )
        except ProductionOrder.DoesNotExist:
            return Response(
                {"errors": "Production order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch_serializer = ProductionBatchSerializer(result["batch"])
        movement_serializer = StockMovementSerializer(result["movements"], many=True)
        plan_serializer = ProductionPlanSerializer(result["plan"])

        return Response(
            {
                "message": "Production started successfully",
                "batch": batch_serializer.data,
                "movements": movement_serializer.data,
                "plan": plan_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )
