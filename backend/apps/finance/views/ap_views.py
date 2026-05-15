from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import BankAccount
from apps.finance.models import AccountsPayable
from apps.finance.serializers.ap_serializers import (
    APSerializer,
    RecordSupplierPaymentSerializer,
    SupplierPaymentSerializer,
)
from apps.finance.services.ap_service import APService


class APListView(APIView):
    """
    GET /finance/ap     list (filter by status, supplier_id, overdue)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - AP"],
        summary="List accounts payable",
        description=(
            "Returns company accounts payable records with optional filtering by "
            "status, supplier, and overdue flag."
        ),
        parameters=[
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by payable status.",
                enum=["open", "partially_paid", "paid", "overdue", "cancelled"],
            ),
            OpenApiParameter(
                name="supplier_id",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by supplier UUID.",
            ),
            OpenApiParameter(
                name="overdue",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="If true, only overdue payables are returned.",
            ),
        ],
        responses={200: APSerializer(many=True)},
    )
    def get(self, request):
        company = request.user.company
        qs = (
            AccountsPayable.objects.filter(supplier_invoice__warehouse__company=company)
            .select_related("supplier", "supplier_invoice", "journal_entry")
            .order_by("-due_date")
        )

        ap_status = request.query_params.get("status")
        supplier_id = request.query_params.get("supplier_id")
        overdue = request.query_params.get("overdue")

        if ap_status:
            qs = qs.filter(status=ap_status)
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        if overdue and overdue.lower() == "true":
            qs = qs.filter(status="overdue")

        return Response(APSerializer(qs, many=True).data)


class APDetailView(APIView):
    """GET /finance/ap/{id}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - AP"],
        summary="Get payable detail",
        description="Returns one accounts payable record including linked payments.",
        responses={200: APSerializer},
    )
    def get(self, request, pk):
        ap = get_object_or_404(
            AccountsPayable.objects.select_related(
                "supplier", "supplier_invoice", "journal_entry"
            ).prefetch_related("payments"),
            pk=pk,
            supplier_invoice__warehouse__company=request.user.company,
        )
        return Response(APSerializer(ap).data)


class APBySupplierView(APIView):
    """GET /finance/ap/supplier/{supplier_id}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - AP"],
        summary="List supplier payables",
        description="Returns accounts payable records scoped to a specific supplier.",
        responses={200: APSerializer(many=True)},
    )
    def get(self, request, supplier_id):
        company = request.user.company
        qs = (
            AccountsPayable.objects.filter(
                supplier_id=supplier_id,
                supplier_invoice__warehouse__company=company,
            )
            .select_related("supplier", "supplier_invoice", "journal_entry")
            .order_by("-due_date")
        )
        return Response(APSerializer(qs, many=True).data)


class APPayView(APIView):
    """POST /finance/ap/{id}/pay"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - AP"],
        summary="Record supplier payment",
        description=(
            "Records a supplier payment, posts the journal entry, and updates payable "
            "balances/status."
        ),
        request=RecordSupplierPaymentSerializer,
        responses={201: SupplierPaymentSerializer},
    )
    def post(self, request, pk):
        ap = get_object_or_404(
            AccountsPayable,
            pk=pk,
            supplier_invoice__warehouse__company=request.user.company,
        )
        serializer = RecordSupplierPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        bank_account = None
        if d.get("bank_account"):
            bank_account = get_object_or_404(
                BankAccount,
                pk=d["bank_account"],
                company=request.user.company,
                is_active=True,
            )
        payment = APService.record_payment(
            ap=ap,
            amount=d["amount"],
            payment_method=d["payment_method"],
            paid_by=request.user,
            bank_account=bank_account,
            reference=d.get("reference", ""),
            notes=d.get("notes", ""),
        )
        return Response(
            SupplierPaymentSerializer(payment).data, status=status.HTTP_201_CREATED
        )
