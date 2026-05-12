from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import JournalEntry
from apps.finance.serializers.journal_serializers import (
    JournalEntryDetailSerializer,
    JournalEntryListSerializer,
    ManualJournalEntrySerializer,
    ReverseJournalSerializer,
)
from apps.finance.services.journal_service import JournalLine, JournalService


class JournalEntryListView(APIView):
    """
    GET  /finance/journal-entries       list
    POST /finance/journal-entries       create manual entry
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - Journals"],
        summary="List journal entries",
        description="Returns journal entries with optional date, type, and reference filters.",
        parameters=[
            OpenApiParameter(
                name="date_from",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Inclusive start date (YYYY-MM-DD).",
            ),
            OpenApiParameter(
                name="date_to",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Inclusive end date (YYYY-MM-DD).",
            ),
            OpenApiParameter(
                name="entry_type",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by entry type.",
                enum=["manual", "automated", "reversal"],
            ),
            OpenApiParameter(
                name="reference_type",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by source reference type.",
            ),
            OpenApiParameter(
                name="fiscal_period_id",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by fiscal period UUID.",
            ),
        ],
        responses={200: JournalEntryListSerializer(many=True)},
    )
    def get(self, request):
        company = request.user.company
        qs = JournalEntry.objects.filter(company=company).order_by(
            "-entry_date", "-created_at"
        )

        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        entry_type = request.query_params.get("entry_type")
        reference_type = request.query_params.get("reference_type")
        fiscal_period_id = request.query_params.get("fiscal_period_id")

        if date_from:
            qs = qs.filter(entry_date__gte=date_from)
        if date_to:
            qs = qs.filter(entry_date__lte=date_to)
        if entry_type:
            qs = qs.filter(entry_type=entry_type)
        if reference_type:
            qs = qs.filter(reference_type=reference_type)
        if fiscal_period_id:
            qs = qs.filter(fiscal_period_id=fiscal_period_id)

        return Response(JournalEntryListSerializer(qs, many=True).data)

    @extend_schema(
        tags=["Finance - Journals"],
        summary="Create manual journal entry",
        description="Creates a balanced manual journal entry in an open fiscal period.",
        request=ManualJournalEntrySerializer,
        responses={201: JournalEntryDetailSerializer},
    )
    def post(self, request):
        serializer = ManualJournalEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        lines = [
            JournalLine(
                account_code=l["account_code"],
                type=l["type"],
                amount=l["amount"],
                description=l.get("description", ""),
            )
            for l in d["lines"]
        ]

        entry = JournalService.post(
            company=request.user.company,
            entry_date=d["entry_date"],
            description=d["description"],
            lines=lines,
            entry_type="manual",
            created_by=request.user,
        )
        return Response(
            JournalEntryDetailSerializer(entry).data, status=status.HTTP_201_CREATED
        )


class JournalEntryDetailView(APIView):
    """GET /finance/journal-entries/{id}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - Journals"],
        summary="Get journal entry",
        description="Returns one journal entry with full lines.",
        responses={200: JournalEntryDetailSerializer},
    )
    def get(self, request, pk):
        entry = get_object_or_404(
            JournalEntry.objects.prefetch_related("lines__account"),
            pk=pk,
            company=request.user.company,
        )
        return Response(JournalEntryDetailSerializer(entry).data)


class JournalEntryReverseView(APIView):
    """POST /finance/journal-entries/{id}/reverse"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - Journals"],
        summary="Reverse journal entry",
        description="Creates an equal-and-opposite reversal entry for the selected journal.",
        request=ReverseJournalSerializer,
        responses={201: JournalEntryDetailSerializer},
    )
    def post(self, request, pk):
        entry = get_object_or_404(JournalEntry, pk=pk, company=request.user.company)
        serializer = ReverseJournalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reversal = JournalService.reverse(
            original_entry=entry,
            reversed_by=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(
            JournalEntryDetailSerializer(reversal).data, status=status.HTTP_201_CREATED
        )
