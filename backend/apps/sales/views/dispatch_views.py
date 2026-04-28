from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.sales.models import Delivery, SalesOrder
from apps.sales.serializers.dispatch_serializers import (
    ConfirmReceiptSerializer,
    DeliveryDetailSerializer,
    DeliveryListSerializer,
    FailDeliverySerializer,
)
from apps.sales.services.dispatch_service import DispatchService


class DeliveryViewSet(ViewSet):
    """
    GET  /deliveries          list all deliveries
    GET  /deliveries/{id}     retrieve delivery with lines
    PATCH /deliveries/{id}/confirm-receipt  mark as delivered
    PATCH /deliveries/{id}/fail             mark as failed
    """

    permission_classes = [IsAuthenticated]

    def list(self, request):
        qs = Delivery.objects.select_related("sales_order", "warehouse").order_by("-dispatched_at")
        delivery_status = request.query_params.get("status")
        warehouse_id = request.query_params.get("warehouse_id")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if delivery_status:
            qs = qs.filter(status=delivery_status)
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if date_from:
            qs = qs.filter(dispatched_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(dispatched_at__date__lte=date_to)
        return Response(DeliveryListSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        delivery = get_object_or_404(
            Delivery.objects.prefetch_related("lines__product", "lines__batch"), pk=pk
        )
        return Response(DeliveryDetailSerializer(delivery).data)

    def confirm_receipt(self, request, pk=None):
        delivery = get_object_or_404(Delivery, pk=pk)
        serializer = ConfirmReceiptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if delivery.status == "delivered":
            return Response({"detail": "Delivery already confirmed."}, status=400)
        delivery.status = "delivered"
        delivery.delivered_at = timezone.now()
        if serializer.validated_data.get("notes"):
            delivery.notes = serializer.validated_data["notes"]
        delivery.save(update_fields=["status", "delivered_at", "notes"])
        return Response(DeliveryDetailSerializer(delivery).data)

    def fail_delivery(self, request, pk=None):
        delivery = get_object_or_404(Delivery, pk=pk)
        serializer = FailDeliverySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        delivery.status = "failed"
        delivery.notes = (
            f"{delivery.notes or ''}\n[Failed: {serializer.validated_data['reason']}]".strip()
        )
        delivery.save(update_fields=["status", "notes"])
        return Response(DeliveryDetailSerializer(delivery).data)


class DispatchOrderView(APIView):
    """
    POST /orders/{order_id}/dispatch
    Initiates dispatch for a confirmed order. Triggers FEFO batch selection,
    stock movements, COGS snapshot, and journal entries.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        order = get_object_or_404(SalesOrder, pk=order_id)
        delivery = DispatchService.dispatch_order(
            order=order,
            created_by=request.user,
        )
        return Response(DeliveryDetailSerializer(delivery).data, status=status.HTTP_201_CREATED)
