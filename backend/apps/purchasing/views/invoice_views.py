from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin

from ..models import SupplierInvoice
from ..serializers.invoice_serializers import (
    InvoiceApproveSerializer,
    InvoiceCreateSerializer,
    InvoiceMarkPaidSerializer,
    InvoiceRejectSerializer,
    MatchResultSerializer,
    SupplierInvoiceSerializer,
)
from ..services.invoice_service import (
    approve_invoice,
    create_invoice,
    mark_paid,
    match_invoice,
    reject_invoice,
)


class SupplierInvoiceViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = SupplierInvoice.objects.select_related(
        "supplier",
        "warehouse",
        "purchase_order",
        "approved_by",
        "rejected_by",
        "paid_by",
    ).prefetch_related("line_items", "line_items__product")
    company_field = "warehouse__company"

    def get_queryset(self):
        queryset = super().get_queryset()

        status_filter = self.request.query_params.get("status")
        supplier_id = self.request.query_params.get("supplier_id")
        po_id = self.request.query_params.get("purchase_order_id")

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        if po_id:
            queryset = queryset.filter(purchase_order_id=po_id)

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return InvoiceCreateSerializer
        return SupplierInvoiceSerializer

    def create(self, request, *args, **kwargs):
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        try:
            invoice = create_invoice(
                po_id=payload["po_id"],
                supplier_id=payload["supplier_id"],
                invoice_date=payload["invoice_date"],
                due_date=payload.get("due_date"),
                lines=payload["lines"],
                created_by=request.user,
            )
        except DjangoValidationError as exc:
            return Response(
                {
                    "errors": (
                        exc.message_dict
                        if hasattr(exc, "message_dict")
                        else exc.messages
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            SupplierInvoiceSerializer(
                invoice, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(responses=MatchResultSerializer)
    @action(detail=True, methods=["get"], url_path="match")
    def match(self, request, pk=None):
        self.get_object()  # ensure exists + permissions
        try:
            result = match_invoice(pk)
        except DjangoValidationError as exc:
            return Response(
                {
                    "errors": (
                        exc.message_dict
                        if hasattr(exc, "message_dict")
                        else exc.messages
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            MatchResultSerializer(result).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=InvoiceApproveSerializer, responses=SupplierInvoiceSerializer
    )
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        self.get_object()
        serializer = InvoiceApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            invoice, match_result = approve_invoice(
                pk, serializer.validated_data["approved_by"]
            )
        except DjangoValidationError as exc:
            return Response(
                {
                    "errors": (
                        exc.message_dict
                        if hasattr(exc, "message_dict")
                        else exc.messages
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = SupplierInvoiceSerializer(
            invoice, context=self.get_serializer_context()
        ).data
        data["match_result"] = MatchResultSerializer(match_result).data

        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(request=InvoiceRejectSerializer, responses=SupplierInvoiceSerializer)
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        self.get_object()
        serializer = InvoiceRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            invoice = reject_invoice(
                pk,
                serializer.validated_data["rejected_by"],
                serializer.validated_data.get("reason", ""),
            )
        except DjangoValidationError as exc:
            return Response(
                {
                    "errors": (
                        exc.message_dict
                        if hasattr(exc, "message_dict")
                        else exc.messages
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            SupplierInvoiceSerializer(
                invoice, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=InvoiceMarkPaidSerializer, responses=SupplierInvoiceSerializer
    )
    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid_action(self, request, pk=None):
        self.get_object()
        serializer = InvoiceMarkPaidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            invoice = mark_paid(
                pk,
                serializer.validated_data["paid_by"],
                serializer.validated_data.get("payment_reference", ""),
            )
        except DjangoValidationError as exc:
            return Response(
                {
                    "errors": (
                        exc.message_dict
                        if hasattr(exc, "message_dict")
                        else exc.messages
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            SupplierInvoiceSerializer(
                invoice, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )
