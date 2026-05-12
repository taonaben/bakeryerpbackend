from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import status
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounting.models import ChartOfAccounts
from apps.finance.serializers.coa_serializers import (
    ChartOfAccountsCreateSerializer,
    ChartOfAccountsSerializer,
    ChartOfAccountsUpdateSerializer,
)
from apps.finance.services.chart_of_accounts_service import ChartOfAccountsService


class ChartOfAccountsListView(APIView):
    """
    GET  /finance/accounts              list (filter by type, subtype, is_active)
    POST /finance/accounts              create
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - Chart Of Accounts"],
        summary="List chart of accounts",
        description=(
            "Returns chart of accounts records for the current company. "
            "Supports type/subtype and active-state filtering."
        ),
        parameters=[
            OpenApiParameter(
                name="account_type",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by account type.",
            ),
            OpenApiParameter(
                name="account_subtype",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by account subtype.",
            ),
            OpenApiParameter(
                name="is_active",
                type=bool,
                location=OpenApiParameter.QUERY,
                description="Filter active/inactive accounts.",
            ),
        ],
        responses={200: ChartOfAccountsSerializer(many=True)},
    )
    def get(self, request):
        company = request.user.company
        qs = ChartOfAccounts.objects.filter(company=company).order_by("code")
        account_type = request.query_params.get("account_type")
        account_subtype = request.query_params.get("account_subtype")
        is_active = request.query_params.get("is_active")
        if account_type:
            qs = qs.filter(account_type=account_type)
        if account_subtype:
            qs = qs.filter(account_subtype=account_subtype)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")
        return Response(ChartOfAccountsSerializer(qs, many=True).data)

    @extend_schema(
        tags=["Finance - Chart Of Accounts"],
        summary="Create chart account",
        description="Creates a new ledger account for the current company.",
        request=ChartOfAccountsCreateSerializer,
        responses={201: ChartOfAccountsSerializer},
    )
    def post(self, request):
        serializer = ChartOfAccountsCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = ChartOfAccountsService.create_account(
            company=request.user.company,
            data=serializer.validated_data,
        )
        return Response(
            ChartOfAccountsSerializer(account).data, status=status.HTTP_201_CREATED
        )


class ChartOfAccountsDetailView(APIView):
    """
    GET    /finance/accounts/{id}
    PATCH  /finance/accounts/{id}
    DELETE /finance/accounts/{id}   soft-delete
    """

    permission_classes = [IsAuthenticated]

    def _get_account(self, request, pk):
        return get_object_or_404(ChartOfAccounts, pk=pk, company=request.user.company)

    @extend_schema(
        tags=["Finance - Chart Of Accounts"],
        summary="Get chart account",
        description="Returns one chart of accounts record.",
        responses={200: ChartOfAccountsSerializer},
    )
    def get(self, request, pk):
        return Response(ChartOfAccountsSerializer(self._get_account(request, pk)).data)

    @extend_schema(
        tags=["Finance - Chart Of Accounts"],
        summary="Update chart account",
        description="Partially updates a chart account. System account code changes are blocked.",
        request=ChartOfAccountsUpdateSerializer,
        responses={200: ChartOfAccountsSerializer},
    )
    def patch(self, request, pk):
        account = self._get_account(request, pk)
        serializer = ChartOfAccountsUpdateSerializer(
            instance=account, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        account = ChartOfAccountsService.update_account(
            account, serializer.validated_data
        )
        return Response(ChartOfAccountsSerializer(account).data)

    @extend_schema(
        tags=["Finance - Chart Of Accounts"],
        summary="Deactivate chart account",
        description="Soft-deletes a non-system account by setting it inactive.",
        responses={204: None},
    )
    def delete(self, request, pk):
        account = self._get_account(request, pk)
        ChartOfAccountsService.deactivate_account(account)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SeedAccountsView(APIView):
    """
    POST /finance/accounts/seed
    Seeds the default system accounts for the company. Idempotent.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Finance - Chart Of Accounts"],
        summary="Seed system accounts",
        description="Creates missing default system accounts for the current company.",
        request=None,
        responses={
            200: inline_serializer(
                name="SeedAccountsResponse",
                fields={
                    "seeded": serializers.IntegerField(),
                    "accounts": ChartOfAccountsSerializer(many=True),
                },
            )
        },
    )
    def post(self, request):
        accounts = ChartOfAccountsService.seed_system_accounts(request.user.company)
        return Response(
            {
                "seeded": len(accounts),
                "accounts": ChartOfAccountsSerializer(accounts, many=True).data,
            },
            status=status.HTTP_200_OK,
        )
