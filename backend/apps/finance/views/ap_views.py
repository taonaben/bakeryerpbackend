from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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

    def get(self, request):
        company = request.user.company
        qs = AccountsPayable.objects.filter(
            supplier_invoice__warehouse__company=company
        ).select_related("supplier", "supplier_invoice", "journal_entry").order_by("-due_date")

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

    def get(self, request, supplier_id):
        company = request.user.company
        qs = AccountsPayable.objects.filter(
            supplier_id=supplier_id,
            supplier_invoice__warehouse__company=company,
        ).select_related("supplier", "supplier_invoice", "journal_entry").order_by("-due_date")
        return Response(APSerializer(qs, many=True).data)


class APPayView(APIView):
    """POST /finance/ap/{id}/pay"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ap = get_object_or_404(
            AccountsPayable,
            pk=pk,
            supplier_invoice__warehouse__company=request.user.company,
        )
        serializer = RecordSupplierPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        payment = APService.record_payment(
            ap=ap,
            amount=d["amount"],
            payment_method=d["payment_method"],
            paid_by=request.user,
            reference=d.get("reference", ""),
            notes=d.get("notes", ""),
        )
        return Response(SupplierPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
