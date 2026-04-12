from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin

from apps.purchasing.models import PurchaseRequisition, PurchaseRequisitionLineItem
from apps.purchasing.serializers.requisition_serilalizer import (
    PurchaseRequisitionApproveSerializer,
    PurchaseRequisitionConvertSerializer,
    PurchaseRequisitionCreateSerializer,
    PurchaseRequisitionLineItemSerializer,
    PurchaseRequisitionRejectSerializer,
    PurchaseRequisitionSerializer,
    PurchaseRequisitionSubmitSerializer,
)
from apps.purchasing.serializers.purchase_order_serializers import (
    PurchaseOrderSerializer,
)
from apps.purchasing.services.requisition_service import (
    approve_requisition,
    convert_to_purchase_order,
    create_requisition,
    reject_requisition,
    submit_requisition,
)


class PurchaseRequisitionViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = PurchaseRequisition.objects.select_related(
        "requested_by",
        "warehouse",
        "submitted_by",
        "approved_by",
        "rejected_by",
    ).prefetch_related("line_items", "line_items__product")
    company_field = "warehouse__company"

    def get_queryset(self):
        queryset = super().get_queryset()

        status_filter = self.request.query_params.get("status")
        warehouse_id = self.request.query_params.get("warehouse_id")
        requested_by_id = self.request.query_params.get("requested_by")

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if requested_by_id:
            queryset = queryset.filter(requested_by_id=requested_by_id)

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return PurchaseRequisitionCreateSerializer
        return PurchaseRequisitionSerializer

    def create(self, request, *args, **kwargs):
        serializer = PurchaseRequisitionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        try:
            requisition = create_requisition(
                requested_by=request.user,
                warehouse_id=payload["warehouse_id"],
                title=payload["title"],
                lines=payload["lines"],
                description=payload.get("description", ""),
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PurchaseRequisitionSerializer(
                requisition, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        requisition = self.get_object()
        if requisition.status != "Draft":
            return Response(
                {"errors": ["Only Draft requisitions can be edited."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    @extend_schema(
        request=PurchaseRequisitionSubmitSerializer,
        responses=PurchaseRequisitionSerializer,
    )
    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        requisition = self.get_object()
        serializer = PurchaseRequisitionSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            requisition = submit_requisition(
                requisition.id, serializer.validated_data["submitted_by"]
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PurchaseRequisitionSerializer(
                requisition, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=PurchaseRequisitionApproveSerializer,
        responses=PurchaseRequisitionSerializer,
    )
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        requisition = self.get_object()
        serializer = PurchaseRequisitionApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            requisition = approve_requisition(
                requisition.id, serializer.validated_data["approved_by"]
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PurchaseRequisitionSerializer(
                requisition, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=PurchaseRequisitionRejectSerializer,
        responses=PurchaseRequisitionSerializer,
    )
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        requisition = self.get_object()
        serializer = PurchaseRequisitionRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            requisition = reject_requisition(
                requisition.id,
                serializer.validated_data["rejected_by"],
                serializer.validated_data.get("reason", ""),
            )
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PurchaseRequisitionSerializer(
                requisition, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=PurchaseRequisitionConvertSerializer,
        responses=PurchaseOrderSerializer,
    )
    @action(detail=True, methods=["post"], url_path="convert")
    def convert(self, request, pk=None):
        requisition = self.get_object()
        serializer = PurchaseRequisitionConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            po = convert_to_purchase_order(
                requisition.id,
                supplier_id=serializer.validated_data["supplier_id"],
                created_by=serializer.validated_data["created_by"],
                line_overrides=serializer.validated_data.get("lines"),
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


class PurchaseRequisitionLineItemViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = PurchaseRequisitionLineItemSerializer
    permission_classes = [IsAuthenticated]
    queryset = PurchaseRequisitionLineItem.objects.select_related(
        "purchase_requisition", "product"
    )
    company_field = "purchase_requisition__warehouse__company"

    def get_queryset(self):
        queryset = super().get_queryset()
        requisition_id = self.request.query_params.get("purchase_requisition_id")
        if requisition_id:
            queryset = queryset.filter(purchase_requisition_id=requisition_id)
        return queryset

    def _ensure_draft(self, requisition):
        if requisition.status != "Draft":
            raise DjangoValidationError(
                "Requisition line items can only be changed in Draft status."
            )

    def perform_create(self, serializer):
        requisition = serializer.validated_data.get("purchase_requisition")
        self._ensure_draft(requisition)
        serializer.save()

    def perform_update(self, serializer):
        requisition = serializer.instance.purchase_requisition
        self._ensure_draft(requisition)
        serializer.save()

    def perform_destroy(self, instance):
        requisition = instance.purchase_requisition
        self._ensure_draft(requisition)
        instance.delete()
