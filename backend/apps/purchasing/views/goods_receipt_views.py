from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin

from ..models import GoodsReceipt
from ..serializers.goods_receipt_serializers import (
    GoodsReceiptConfirmSerializer,
    GoodsReceiptCreateSerializer,
    GoodsReceiptRejectSerializer,
    GoodsReceiptSerializer,
)
from ..services.goods_receipt_service import GoodsReceiptService


class GoodsReceiptViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = GoodsReceiptSerializer
    queryset = GoodsReceipt.objects.select_related(
        "purchase_order",
        "warehouse",
        "received_by",
    ).prefetch_related("line_items", "line_items__product", "line_items__po_line_item")
    company_field = "warehouse__company"

    def get_queryset(self):
        queryset = super().get_queryset()

        po_id = self.request.query_params.get("purchase_order_id")
        warehouse_id = self.request.query_params.get("warehouse_id")
        status_filter = self.request.query_params.get("status")

        if po_id:
            queryset = queryset.filter(purchase_order_id=po_id)
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return GoodsReceiptCreateSerializer
        return GoodsReceiptSerializer

    def create(self, request, *args, **kwargs):
        serializer = GoodsReceiptCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        try:
            grn = GoodsReceiptService.create_grn(
                po_id=payload["purchase_order_id"],
                warehouse_id=payload["warehouse_id"],
                received_by=payload["received_by"],
                lines=payload["lines"],
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            GoodsReceiptSerializer(grn, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=GoodsReceiptConfirmSerializer, responses=GoodsReceiptSerializer
    )
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        grn = self.get_object()
        serializer = GoodsReceiptConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            grn = GoodsReceiptService.confirm_grn(
                grn.id, serializer.validated_data.get("confirmed_by")
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            GoodsReceiptSerializer(grn, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=GoodsReceiptRejectSerializer, responses=GoodsReceiptSerializer
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        grn = self.get_object()
        serializer = GoodsReceiptRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            grn = GoodsReceiptService.reject_grn(
                grn.id,
                rejected_by=serializer.validated_data.get("rejected_by"),
                reason=serializer.validated_data.get("reason", ""),
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            GoodsReceiptSerializer(grn, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )
