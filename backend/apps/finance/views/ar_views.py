from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.models import AccountsReceivable
from apps.finance.serializers.ar_serializers import ARSerializer


class ARListView(APIView):
    """
    GET /finance/ar     list (filter by status, customer_id, overdue)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - AR"],
        summary="List accounts receivable",
        description=(
            "Returns company receivables with optional filtering by status, "
            "customer, and overdue flag."
        ),
        parameters=[
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by receivable status.",
                enum=["open", "partially_paid", "paid", "overdue", "cancelled"],
            ),
            OpenApiParameter(
                name="customer_id",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by customer UUID.",
            ),
            OpenApiParameter(
                name="overdue",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="If true, only overdue receivables are returned.",
            ),
        ],
        responses={200: ARSerializer(many=True)},
    )
    def get(self, request):
        company = request.user.company
        qs = (
            AccountsReceivable.objects.filter(
                invoice__sales_order__warehouse__company=company
            )
            .select_related("customer", "invoice", "journal_entry")
            .order_by("-due_date")
        )

        ar_status = request.query_params.get("status")
        customer_id = request.query_params.get("customer_id")
        overdue = request.query_params.get("overdue")

        if ar_status:
            qs = qs.filter(status=ar_status)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if overdue and overdue.lower() == "true":
            qs = qs.filter(status="overdue")

        return Response(ARSerializer(qs, many=True).data)


class ARDetailView(APIView):
    """GET /finance/ar/{id}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - AR"],
        summary="Get receivable detail",
        description="Returns one accounts receivable record.",
        responses={200: ARSerializer},
    )
    def get(self, request, pk):
        ar = get_object_or_404(
            AccountsReceivable.objects.select_related(
                "customer", "invoice", "journal_entry"
            ),
            pk=pk,
            invoice__sales_order__warehouse__company=request.user.company,
        )
        return Response(ARSerializer(ar).data)


class ARByCustomerView(APIView):
    """GET /finance/ar/customer/{customer_id}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - AR"],
        summary="List customer receivables",
        description="Returns receivables for the specified customer.",
        responses={200: ARSerializer(many=True)},
    )
    def get(self, request, customer_id):
        company = request.user.company
        qs = (
            AccountsReceivable.objects.filter(
                customer_id=customer_id,
                invoice__sales_order__warehouse__company=company,
            )
            .select_related("customer", "invoice", "journal_entry")
            .order_by("-due_date")
        )
        return Response(ARSerializer(qs, many=True).data)
