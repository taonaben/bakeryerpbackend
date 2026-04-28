from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.sales.models import Customer, Delivery, SalesOrder, SalesOrderLine
from apps.sales.serializers.dispatch_serializers import DeliveryListSerializer
from apps.sales.serializers.sales_order_serializer import (
    AddLineSerializer,
    CancelOrderSerializer,
    POSSaleSerializer,
    SalesOrderCreateSerializer,
    SalesOrderDetailSerializer,
    SalesOrderListSerializer,
    SalesOrderUpdateSerializer,
    UpdateLineSerializer,
)
from apps.sales.services.sales_order_service import SalesOrderService
from apps.sales.services.customer_service import CustomerService
from central.models import Product, Warehouse


class SalesOrderViewSet(viewsets.ViewSet):
    """
    GET    /orders                      list
    POST   /orders                      create draft order
    GET    /orders/{id}                 retrieve with lines
    PATCH  /orders/{id}                 update header fields
    POST   /orders/{id}/lines           add line
    PATCH  /orders/{id}/lines/{line_id} update line quantity
    DELETE /orders/{id}/lines/{line_id} remove line
    POST   /orders/{id}/confirm         confirm order
    POST   /orders/{id}/cancel          cancel order
    GET    /orders/{id}/deliveries      deliveries for this order
    POST   /orders/pos                  POS fast path
    """

    permission_classes = [IsAuthenticated]

    def list(self, request):
        qs = SalesOrder.objects.select_related("customer", "warehouse").order_by("-created_at")
        order_type = request.query_params.get("order_type")
        order_status = request.query_params.get("status")
        warehouse_id = request.query_params.get("warehouse_id")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if order_type:
            qs = qs.filter(order_type=order_type)
        if order_status:
            qs = qs.filter(status=order_status)
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if date_from:
            qs = qs.filter(order_date__date__gte=date_from)
        if date_to:
            qs = qs.filter(order_date__date__lte=date_to)
        return Response(SalesOrderListSerializer(qs, many=True).data)

    def create(self, request):
        serializer = SalesOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        customer = get_object_or_404(Customer, pk=d["customer_id"])
        warehouse = get_object_or_404(Warehouse, pk=d["warehouse_id"])
        order = SalesOrderService.create_order(
            customer=customer,
            warehouse=warehouse,
            created_by=request.user,
            expected_delivery_date=d.get("expected_delivery_date"),
            delivery_address=d.get("delivery_address", ""),
            notes=d.get("notes", ""),
        )
        return Response(SalesOrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        order = get_object_or_404(
            SalesOrder.objects.prefetch_related("lines__product"), pk=pk
        )
        return Response(SalesOrderDetailSerializer(order).data)

    def partial_update(self, request, pk=None):
        order = get_object_or_404(SalesOrder, pk=pk)
        serializer = SalesOrderUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(order, field, value)
        order.save()
        return Response(SalesOrderDetailSerializer(order).data)

    @action(detail=True, methods=["post"], url_path="lines")
    def add_line(self, request, pk=None):
        order = get_object_or_404(SalesOrder, pk=pk)
        serializer = AddLineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_object_or_404(Product, pk=serializer.validated_data["product_id"])
        line = SalesOrderService.add_line(
            order=order,
            product=product,
            quantity=serializer.validated_data["quantity"],
        )
        from apps.sales.serializers.sales_order_serializer import SalesOrderLineSerializer
        data = SalesOrderLineSerializer(line).data
        if hasattr(line, "_stock_warning"):
            data["warning"] = line._stock_warning
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch", "delete"], url_path=r"lines/(?P<line_id>[^/.]+)")
    def line_detail(self, request, pk=None, line_id=None):
        order = get_object_or_404(SalesOrder, pk=pk)
        line = get_object_or_404(SalesOrderLine, pk=line_id, sales_order=order)

        if request.method == "DELETE":
            SalesOrderService.remove_line(order=order, line=line)
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = UpdateLineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Remove and re-add with new quantity to go through pricing logic
        SalesOrderService.remove_line(order=order, line=line)
        new_line = SalesOrderService.add_line(
            order=order,
            product=line.product,
            quantity=serializer.validated_data["quantity"],
        )
        from apps.sales.serializers.sales_order_serializer import SalesOrderLineSerializer
        return Response(SalesOrderLineSerializer(new_line).data)

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        order = get_object_or_404(SalesOrder, pk=pk)
        order = SalesOrderService.confirm_order(order)
        return Response(SalesOrderDetailSerializer(order).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        order = get_object_or_404(SalesOrder, pk=pk)
        serializer = CancelOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = SalesOrderService.cancel_order(
            order=order,
            cancelled_by=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(SalesOrderDetailSerializer(order).data)

    @action(detail=True, methods=["get"], url_path="deliveries")
    def deliveries(self, request, pk=None):
        order = get_object_or_404(SalesOrder, pk=pk)
        deliveries = Delivery.objects.filter(sales_order=order).order_by("-dispatched_at")
        return Response(DeliveryListSerializer(deliveries, many=True).data)

    @action(detail=False, methods=["post"], url_path="pos")
    def pos_sale(self, request):
        """
        POST /orders/pos — complete POS sale in one atomic call.
        Creates order, adds lines, confirms (triggers dispatch + invoice + payment).
        """
        serializer = POSSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        # Use Cash Customer if no customer_id provided
        if d.get("customer_id"):
            customer = get_object_or_404(Customer, pk=d["customer_id"])
        else:
            customer = CustomerService.get_or_create_cash_customer()

        warehouse = get_object_or_404(Warehouse, pk=d["warehouse_id"])

        order = SalesOrderService.create_order(
            customer=customer,
            warehouse=warehouse,
            created_by=request.user,
        )

        for line_data in d["lines"]:
            product = get_object_or_404(Product, pk=line_data["product_id"])
            SalesOrderService.add_line(
                order=order, product=product, quantity=line_data["quantity"]
            )

        # Patch payment method onto the order so _pos_fast_path can use it
        order._pos_payment_method = d.get("payment_method", "cash")

        order = SalesOrderService.confirm_order(order)
        order.refresh_from_db()
        return Response(SalesOrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)
