from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets, status

from ..services.batch_service import ProductionBatchService
from ..services.production_engine import ProductionEngine

from ..models import ProductionOrder, BatchOutput, BatchWaste
from apps.inventory.serializers import StockMovementSerializer


from ..serializers import (
    ProductionOrderSerializer,
    ProductionPlanSerializer,
    StartProductionSerializer,
    ProductionBatchSerializer,
    FinishProductionSerializer,
    FinishProductionSummarySerializer,
    BatchOutputSerializer,
    BatchWasteSerializer,
    ProductionOrderFinishedSerializer,
)


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

    def _summary_queryset(self):
        return (
            self.get_queryset()
            .select_related("product", "warehouse", "formula")
            .prefetch_related(
                "batches__lines",
                "batches__materials",
                "batches__outputs",
                "batches__waste",
            )
        )

    @action(
        detail=False, methods=["post"], url_path="copy/(?P<production_order_id>[^/.]+)"
    )
    def copy_order(self, request, pk=None, production_order_id=None):
        """create a new production order by copying an existing one"""

        original_order = get_object_or_404(ProductionOrder, id=production_order_id)

        new_order = ProductionOrder.objects.create(
            product=original_order.product,
            quantity=original_order.quantity,
            warehouse=original_order.warehouse,
            formula=original_order.formula,
        )

        if request.data:
            update_serializer = ProductionOrderSerializer(
                new_order, data=request.data, partial=True
            )
            update_serializer.is_valid(raise_exception=True)
            new_order = update_serializer.save()

        serializer = ProductionOrderSerializer(new_order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="finished")
    def finished_orders(self, request):
        queryset = self._summary_queryset().filter(status="completed")
        serializer = ProductionOrderFinishedSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="summary")
    def order_summary(self, request, pk=None):
        order = get_object_or_404(self._summary_queryset(), id=pk, status="completed")
        serializer = ProductionOrderFinishedSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductionStartAPIView(APIView):
    """API view to handle starting a production order with optional batch selection"""

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


class ProductionFinishAPIView(APIView):
    """API view to handle finishing a production order with detailed output and waste tracking"""

    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(ProductionOrder, id=order_id)

        expected_output, expected_waste = ProductionBatchService._compute_expectations(
            order
        )

        return Response(
            {
                "expected_output": expected_output,
                "expected_waste": expected_waste,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, order_id):
        if "actual_output" in request.data:
            order = get_object_or_404(ProductionOrder, id=order_id)
            serializer = FinishProductionSummarySerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            outputs = [
                {
                    "product": order.product,
                    "quantity": serializer.validated_data["actual_output"],
                }
            ]
            waste = []
            waste_qty = serializer.validated_data.get("waste")
            if waste_qty and waste_qty > 0:
                waste = [
                    {
                        "product": order.product,
                        "quantity": waste_qty,
                    }
                ]
        else:
            serializer = FinishProductionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            outputs = serializer.validated_data["outputs"]
            waste = serializer.validated_data.get("waste", [])

        try:
            result = ProductionBatchService.finish_order(
                order_id=order_id,
                outputs=outputs,
                waste=waste,
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

        batch = result["batch"]
        outputs = BatchOutput.objects.filter(production_batch=batch)
        waste = BatchWaste.objects.filter(production_batch=batch)

        batch_serializer = ProductionBatchSerializer(batch)
        movement_serializer = StockMovementSerializer(result["movement"])
        output_serializer = BatchOutputSerializer(outputs, many=True)
        waste_serializer = BatchWasteSerializer(waste, many=True)

        return Response(
            {
                "message": "Production finished successfully",
                "batch": batch_serializer.data,
                "movement": movement_serializer.data,
                "outputs": output_serializer.data,
                "waste": waste_serializer.data,
                "expected_output": result["expected_output"],
                "expected_waste": result["expected_waste"],
                "actual_output": result["actual_output"],
                "variance": result["variance"],
            },
            status=status.HTTP_200_OK,
        )
