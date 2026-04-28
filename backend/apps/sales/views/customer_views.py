from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin
from apps.sales.models import Customer, CustomerProduct, Invoice, SalesOrder
from apps.sales.serializers.customer_serializer import (
    CustomerCreateSerializer,
    CustomerDetailSerializer,
    CustomerListSerializer,
    CustomerOutstandingSerializer,
    CustomerProductCreateSerializer,
    CustomerProductSerializer,
    CustomerProductUpdateSerializer,
    CustomerUpdateSerializer,
)
from apps.sales.serializers.invoice_serializers import InvoiceListSerializer
from apps.sales.serializers.sales_order_serializer import SalesOrderListSerializer
from apps.sales.serializers.payment_serializers import PaymentSerializer
from apps.sales.services.customer_service import CustomerService


class CustomerViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    """
    GET    /customers                  list
    POST   /customers                  create
    GET    /customers/{id}             retrieve
    PATCH  /customers/{id}             update
    DELETE /customers/{id}             soft-delete (is_active=False)
    GET    /customers/{id}/orders      orders for this customer
    GET    /customers/{id}/invoices    invoices for this customer
    GET    /customers/{id}/outstanding outstanding balance vs credit limit
    GET    /customers/{id}/pricing     pricing agreements
    POST   /customers/{id}/pricing     create pricing agreement
    PATCH  /customers/{id}/pricing/{agreement_id}  update agreement
    DELETE /customers/{id}/pricing/{agreement_id}  deactivate agreement
    """

    permission_classes = [IsAuthenticated]
    queryset = Customer.objects.all()
    company_field = "sales_orders__warehouse__company"
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Customer.objects.all()
        customer_type = self.request.query_params.get("customer_type")
        is_active = self.request.query_params.get("is_active")
        if customer_type:
            qs = qs.filter(customer_type=customer_type)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")
        return qs.order_by("name")

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerListSerializer
        if self.action == "create":
            return CustomerCreateSerializer
        if self.action in ("partial_update", "update"):
            return CustomerUpdateSerializer
        return CustomerDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = CustomerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = CustomerService.create_customer(serializer.validated_data)
        return Response(CustomerDetailSerializer(customer).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        customer = self.get_object()
        serializer = CustomerUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        customer = CustomerService.update_customer(customer, serializer.validated_data)
        data = CustomerDetailSerializer(customer).data
        if hasattr(customer, "_credit_limit_warning"):
            data["warning"] = customer._credit_limit_warning
        return Response(data)

    def destroy(self, request, *args, **kwargs):
        customer = self.get_object()
        CustomerService.deactivate_customer(customer)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="orders")
    def orders(self, request, pk=None):
        customer = self.get_object()
        orders = SalesOrder.objects.filter(customer=customer).order_by("-created_at")
        return Response(SalesOrderListSerializer(orders, many=True).data)

    @action(detail=True, methods=["get"], url_path="invoices")
    def invoices(self, request, pk=None):
        customer = self.get_object()
        invoices = Invoice.objects.filter(
            sales_order__customer=customer
        ).order_by("-created_at")
        return Response(InvoiceListSerializer(invoices, many=True).data)

    @action(detail=True, methods=["get"], url_path="payments")
    def payments(self, request, pk=None):
        from apps.sales.models import Payment
        customer = self.get_object()
        payments = Payment.objects.filter(customer=customer).order_by("-payment_date")
        return Response(PaymentSerializer(payments, many=True).data)

    @action(detail=True, methods=["get"], url_path="outstanding")
    def outstanding(self, request, pk=None):
        customer = self.get_object()
        balance = CustomerService._outstanding_balance(customer)
        credit_limit = customer.credit_limit
        available = (credit_limit - balance) if credit_limit is not None else None
        data = {
            "customer_id": customer.id,
            "customer_name": customer.name,
            "credit_limit": credit_limit,
            "outstanding_balance": balance,
            "available_credit": available,
            "over_limit": (credit_limit is not None and balance > credit_limit),
        }
        return Response(CustomerOutstandingSerializer(data).data)

    @action(detail=True, methods=["get", "post"], url_path="pricing")
    def pricing(self, request, pk=None):
        customer = self.get_object()
        if request.method == "GET":
            agreements = CustomerProduct.objects.filter(customer=customer).order_by("-valid_from")
            return Response(CustomerProductSerializer(agreements, many=True).data)

        serializer = CustomerProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        agreement = CustomerProduct.objects.create(
            customer=customer, **serializer.validated_data
        )
        return Response(CustomerProductSerializer(agreement).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"pricing/(?P<agreement_id>[^/.]+)",
    )
    def pricing_detail(self, request, pk=None, agreement_id=None):
        customer = self.get_object()
        agreement = get_object_or_404(CustomerProduct, pk=agreement_id, customer=customer)

        if request.method == "DELETE":
            agreement.is_active = False
            agreement.save(update_fields=["is_active"])
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = CustomerProductUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(agreement, field, value)
        agreement.save()
        return Response(CustomerProductSerializer(agreement).data)
