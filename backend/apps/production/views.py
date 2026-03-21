from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework import viewsets, status, generics

from .models import ProductionOrder
from .serializers import ProductionOrderSerializer, ProductionPlanSerializer
from .services.production_planner import ProductionPlanner


class ProductionPlanAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        order = get_object_or_404(ProductionOrder, id=order_id)

        try:
            plan = ProductionPlanner.plan(order)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict or exc.messages)

        serializer = ProductionPlanSerializer(plan)
        return Response(serializer.data)


class ProductionOrderViewSet(viewsets.ModelViewSet):
    serializer_class = ProductionOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get Production orders in Warehouse and optionally filter by status & product"""

        queryset = super().get_queryset()
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
