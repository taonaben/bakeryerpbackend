from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.sales.models import Invoice, SalesOrder
from apps.sales.serializers.invoice_serializers import (
    CancelInvoiceSerializer,
    InvoiceDetailSerializer,
    InvoiceListSerializer,
)
from apps.sales.services.invoice_service import InvoiceService


class InvoiceViewSet(ViewSet):
    """
    GET  /invoices          list (filterable by status, customer, date, overdue)
    GET  /invoices/{id}     retrieve with line breakdown
    POST /invoices/{id}/cancel  cancel invoice
    """

    permission_classes = [IsAuthenticated]

    def list(self, request):
        qs = Invoice.objects.select_related(
            "sales_order__customer", "sales_order__warehouse"
        ).order_by("-created_at")

        invoice_status = request.query_params.get("status")
        customer_id = request.query_params.get("customer_id")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        overdue = request.query_params.get("overdue")

        if invoice_status:
            qs = qs.filter(status=invoice_status)
        if customer_id:
            qs = qs.filter(sales_order__customer_id=customer_id)
        if date_from:
            qs = qs.filter(issued_date__gte=date_from)
        if date_to:
            qs = qs.filter(issued_date__lte=date_to)
        if overdue and overdue.lower() == "true":
            qs = qs.filter(status="overdue")

        return Response(InvoiceListSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        invoice = get_object_or_404(
            Invoice.objects.select_related(
                "sales_order__customer"
            ).prefetch_related("sales_order__lines__product"),
            pk=pk,
        )
        return Response(InvoiceDetailSerializer(invoice).data)

    def cancel(self, request, pk=None):
        invoice = get_object_or_404(Invoice, pk=pk)
        serializer = CancelInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = InvoiceService.cancel_invoice(
            invoice=invoice,
            cancelled_by=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(InvoiceDetailSerializer(invoice).data)


class OrderInvoiceView(APIView):
    """
    GET  /orders/{order_id}/invoice          get invoice for an order
    POST /orders/{order_id}/invoice/generate manually generate invoice (B2B)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(SalesOrder, pk=order_id)
        if not hasattr(order, "invoice"):
            return Response(
                {"detail": "No invoice exists for this order yet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(InvoiceDetailSerializer(order.invoice).data)

    def post(self, request, order_id):
        order = get_object_or_404(SalesOrder, pk=order_id)
        invoice = InvoiceService.create_invoice(order=order, created_by=request.user)
        return Response(InvoiceDetailSerializer(invoice).data, status=status.HTTP_201_CREATED)


class InvoicePDFView(APIView):
    """
    GET /invoices/{id}/pdf — placeholder for PDF generation.
    Returns invoice data; wire up a PDF library (WeasyPrint/ReportLab) here.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        # TODO: render to PDF using WeasyPrint or ReportLab
        # For now return the structured data the PDF template would consume
        return Response({
            "detail": "PDF generation not yet implemented.",
            "invoice": InvoiceDetailSerializer(invoice).data,
        })
