from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets, status

from ..models import ReworkOrder
from apps.inventory.serializers import StockMovementSerializer

from ..serializers import (
    ReworkOrderSerializer,
    ReworkOrderDetailSerializer,
    StartReworkSerializer,
    FinishReworkSerializer,
)
from ..services.rework_service import ReworkService


class ReworkOrderViewSet(viewsets.ModelViewSet):
    """Rework orders to track reprocessing of inventory lots that did not meet quality standards or require correction"""

    serializer_class = ReworkOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = ReworkOrder.objects.all()
        warehouse_id = self.request.query_params.get("warehouse_id")
        status_value = self.request.query_params.get("status")
        product_id = self.request.query_params.get("product_id")

        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if product_id:
            queryset = queryset.filter(target_product_id=product_id)

        return queryset

    def get_serializer_class(self):
        if self.action in ["retrieve", "list"]:
            return ReworkOrderDetailSerializer
        return ReworkOrderSerializer


class ReworkStartAPIView(APIView):
    """API view to handle starting a rework order by consuming existing inventory batches"""

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        serializer = StartReworkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = ReworkService.start_rework(
                order_id=order_id,
                inputs=serializer.validated_data.get("inputs"),
            )
        except ReworkOrder.DoesNotExist:
            return Response(
                {"errors": "Rework order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order_serializer = ReworkOrderDetailSerializer(result["order"])
        movement_serializer = StockMovementSerializer(result["movement"])

        return Response(
            {
                "message": "Rework started successfully",
                "order": order_serializer.data,
                "movement": movement_serializer.data,
                "total_input": result["total_input"],
            },
            status=status.HTTP_201_CREATED,
        )


class ReworkFinishAPIView(APIView):
    """API view to handle finishing a rework order by producing outputs and updating inventory"""

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        serializer = FinishReworkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = ReworkService.finish_rework(
                order_id=order_id,
                outputs=serializer.validated_data.get("outputs"),
            )
        except ReworkOrder.DoesNotExist:
            return Response(
                {"errors": "Rework order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order_serializer = ReworkOrderDetailSerializer(result["order"])
        movement_serializer = StockMovementSerializer(result["movement"])

        return Response(
            {
                "message": "Rework finished successfully",
                "order": order_serializer.data,
                "movement": movement_serializer.data,
                "total_output": result["total_output"],
            },
            status=status.HTTP_200_OK,
        )
