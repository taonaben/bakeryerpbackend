from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import PlannedOrder
from .serializers import (
    PlannedOrderPriorityApprovalSerializer,
    PlannedOrderPriorityApproveResponseSerializer,
    PlannedOrderPriorityApproveSerializer,
    PlannedOrderProductionPlanResponseSerializer,
    PlannedOrderProductionCreateSerializer,
    PlannedOrderSerializer,
)
from apps.production.serializers import ProductionOrderSerializer
from .services.order_services import (
    approve_priority_override,
    build_priority_approval_payload,
    create_production_order_and_plan,
    create_production_order_from_planned,
    get_queue_positions,
    get_queue_queryset,
)


class PlannedOrderViewSet(viewsets.ModelViewSet):
    serializer_class = PlannedOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = PlannedOrder.objects.select_related(
            "product", "warehouse", "priority_override_approved_by"
        )
        warehouse_id = self.request.query_params.get("warehouse_id")
        status_filter = self.request.query_params.get("status")
        product_id = self.request.query_params.get("product_id")
        priority = self.request.query_params.get("priority")

        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if priority:
            queryset = queryset.filter(priority=priority)

        return queryset

    def _queue_queryset(self):
        return get_queue_queryset(
            PlannedOrder.objects.all(),
            self.request.query_params.get("warehouse_id"),
        )

    def _queue_positions(self):
        return get_queue_positions(self._queue_queryset())

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action in ["list", "retrieve"]:
            context["queue_positions"] = self._queue_positions()
        return context

    @extend_schema(responses=PlannedOrderPriorityApprovalSerializer)
    @action(detail=True, methods=["get"], url_path="priority-approval")
    def priority_approval(self, request, pk=None):
        """Endpoint to check if a planned order can request priority override and its current queue position."""
        planned_order = self.get_object()
        payload = build_priority_approval_payload(
            planned_order, self._queue_positions()
        )
        return Response(payload, status=status.HTTP_200_OK)

    @extend_schema(
        request=PlannedOrderPriorityApproveSerializer,
        responses=PlannedOrderPriorityApproveResponseSerializer,
    )
    @action(detail=True, methods=["post"], url_path="priority-approve")
    def priority_approve(self, request, pk=None):
        """Endpoint to approve or revoke priority override for a planned order.

        \n The request body should include 'approve' (boolean) and optional 'note' (string) fields.
        """
        planned_order = self.get_object()
        approve = request.data.get("approve") is True
        note = request.data.get("note")

        try:
            approve_priority_override(planned_order, request.user, approve, note)
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Priority override approved.",
                "queue_position": self._queue_positions().get(str(planned_order.id)),
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=PlannedOrderProductionCreateSerializer,
        responses={201: ProductionOrderSerializer},
    )
    @action(detail=True, methods=["post"], url_path="create-production")
    def create_production(self, request, pk=None):
        """This endpoint creates a production order from the planned order.

        \n The request body should include 'scheduled_start' and 'scheduled_end' fields in ISO 8601 format.

        """
        planned_order = self.get_object()
        serializer = PlannedOrderProductionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scheduled_start = serializer.validated_data["scheduled_start"]
        scheduled_end = serializer.validated_data["scheduled_end"]

        try:
            serializer = create_production_order_from_planned(
                planned_order, scheduled_start, scheduled_end
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=PlannedOrderProductionCreateSerializer,
        responses={201: PlannedOrderProductionPlanResponseSerializer},
    )
    @action(detail=True, methods=["post"], url_path="create-production-plan")
    def create_production_plan(self, request, pk=None):
        """This endpoint creates a production order from the planned order and returns the production plan data."""
        planned_order = self.get_object()
        serializer = PlannedOrderProductionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scheduled_start = serializer.validated_data["scheduled_start"]
        scheduled_end = serializer.validated_data["scheduled_end"]

        try:
            serializer, plan_data = create_production_order_and_plan(
                planned_order, scheduled_start, scheduled_end
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "production_order": serializer.data,
                "plan": plan_data,
            },
            status=status.HTTP_201_CREATED,
        )
