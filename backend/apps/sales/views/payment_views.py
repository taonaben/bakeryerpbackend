from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.sales.models import Customer, Invoice, Payment
from apps.sales.serializers.payment_serializers import PaymentSerializer, RecordPaymentSerializer
from apps.sales.services.payment_service import PaymentService


class PaymentViewSet(ViewSet):
    """
    GET /payments   list all payments (filterable by date, method, customer)
    """

    permission_classes = [IsAuthenticated]

    def list(self, request):
        qs = Payment.objects.select_related(
            "invoice", "customer"
        ).order_by("-payment_date")

        customer_id = request.query_params.get("customer_id")
        payment_method = request.query_params.get("payment_method")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if payment_method:
            qs = qs.filter(payment_method=payment_method)
        if date_from:
            qs = qs.filter(payment_date__date__gte=date_from)
        if date_to:
            qs = qs.filter(payment_date__date__lte=date_to)

        return Response(PaymentSerializer(qs, many=True).data)


class InvoicePaymentView(APIView):
    """
    GET  /invoices/{invoice_id}/payments   list payments for an invoice
    POST /invoices/{invoice_id}/payments   record a payment
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, pk=invoice_id)
        payments = invoice.payments.order_by("-payment_date")
        return Response(PaymentSerializer(payments, many=True).data)

    def post(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, pk=invoice_id)
        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        payment = PaymentService.record_payment(
            invoice=invoice,
            amount=d["amount"],
            payment_method=d["payment_method"],
            received_by=request.user,
            reference=d.get("reference", ""),
            notes=d.get("notes", ""),
            allow_overpayment=d.get("allow_overpayment", False),
        )
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
