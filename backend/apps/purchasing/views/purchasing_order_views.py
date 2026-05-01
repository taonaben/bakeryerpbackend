from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin

from ..models import PurchaseOrder, PurchaseOrderLineItem
from ..serializers.purchase_order_serializers import (
    PurchaseOrderApproveSerializer,
    PurchaseOrderCancelSerializer,
    PurchaseOrderCreateSerializer,
    PurchaseOrderLineItemSerializer,
    PurchaseOrderRejectSerializer,
    PurchaseOrderSerializer,
    PurchaseOrderSubmitSerializer,
)
from ..services.purchase_order_service import (
    approve_po,
    cancel_po,
    create_purchase_order,
    recalculate_total,
    reject_po,
    submit_po,
)


class PurchaseOrderViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = PurchaseOrder.objects.select_related(
        "supplier",
        "warehouse",
        "created_by",
        "submitted_by",
        "approved_by",
        "rejected_by",
        "cancelled_by",
    ).prefetch_related("line_items", "line_items__product", "line_items__supplier")
    company_field = "warehouse__company"

    def get_queryset(self):
        queryset = super().get_queryset()

        status_filter = self.request.query_params.get("status")
        supplier_id = self.request.query_params.get("supplier_id")
        warehouse_id = self.request.query_params.get("warehouse_id")

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return PurchaseOrderCreateSerializer
        return PurchaseOrderSerializer

    def create(self, request, *args, **kwargs):
        serializer = PurchaseOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        try:
            po = create_purchase_order(
                warehouse_id=payload["warehouse_id"],
                lines=payload["lines"],
                created_by=request.user,
                supplier_id=payload.get("supplier_id"),
                pr_id=payload.get("purchase_requisition_id"),
                currency=payload.get("currency"),
                description=payload.get("description", ""),
                expected_delivery_date=payload.get("expected_delivery_date"),
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PurchaseOrderSerializer(po, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        po = self.get_object()
        if po.status != "Draft":
            return Response(
                {"errors": ["Only Draft purchase orders can be edited."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    @extend_schema(
        request=PurchaseOrderSubmitSerializer, responses=PurchaseOrderSerializer
    )
    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        po = self.get_object()
        serializer = PurchaseOrderSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            po = submit_po(po.id, serializer.validated_data["submitted_by"])
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PurchaseOrderSerializer(po, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=PurchaseOrderApproveSerializer, responses=PurchaseOrderSerializer
    )
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        po = self.get_object()
        serializer = PurchaseOrderApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            po = approve_po(po.id, serializer.validated_data["approved_by"])
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PurchaseOrderSerializer(po, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=PurchaseOrderRejectSerializer, responses=PurchaseOrderSerializer
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        po = self.get_object()
        serializer = PurchaseOrderRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            po = reject_po(
                po.id,
                serializer.validated_data["rejected_by"],
                serializer.validated_data.get("reason", ""),
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PurchaseOrderSerializer(po, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=PurchaseOrderCancelSerializer, responses=PurchaseOrderSerializer
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        po = self.get_object()
        serializer = PurchaseOrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            po = cancel_po(po.id, serializer.validated_data["cancelled_by"])
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PurchaseOrderSerializer(po, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses=PurchaseOrderSerializer)
    @action(detail=True, methods=["post"], url_path="recalculate-total")
    def recalc_total(self, request, pk=None):
        po = self.get_object()
        po = recalculate_total(po.id)
        return Response(
            PurchaseOrderSerializer(po, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )


class PurchaseOrderLineItemViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = PurchaseOrderLineItemSerializer
    permission_classes = [IsAuthenticated]
    queryset = PurchaseOrderLineItem.objects.select_related("purchase_order", "product")
    company_field = "purchase_order__warehouse__company"

    def get_queryset(self):
        queryset = super().get_queryset()
        po_id = self.request.query_params.get("purchase_order_id")
        if po_id:
            queryset = queryset.filter(purchase_order_id=po_id)
        return queryset

    def _ensure_draft(self, purchase_order):
        if purchase_order.status != "Draft":
            raise DjangoValidationError(
                "Line items can only be changed in Draft status."
            )

    def perform_create(self, serializer):
        purchase_order = serializer.validated_data.get("purchase_order")
        self._ensure_draft(purchase_order)
        serializer.save()
        recalculate_total(purchase_order.id)

    def perform_update(self, serializer):
        purchase_order = serializer.instance.purchase_order
        self._ensure_draft(purchase_order)
        serializer.save()
        recalculate_total(purchase_order.id)

    def perform_destroy(self, instance):
        purchase_order = instance.purchase_order
        self._ensure_draft(purchase_order)
        instance.delete()
        recalculate_total(purchase_order.id)
