from django.shortcuts import render
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from .models import Formula
from drf_spectacular.utils import extend_schema, OpenApiParameter

# from ..filters import StockFilter, StockMovementFilter, BatchFilter
from .serializers import FormulaSerializer, FormulaCreateSerializer


class FormulaViewSet(viewsets.ModelViewSet):
    serializer_class = FormulaSerializer
    permission_classes = [IsAuthenticated]

    ordering_fields = ["created_at", "product__name"]
    search_fields = ["product__name", "revision"]
    tags = ["Formulas"]

    def get_queryset(self):
        """Filter formulas by product if provided"""
        queryset = Formula.objects.filter(product__company=self.request.user.company)
        product_id = self.request.query_params.get("product_id", None)

        if product_id is not None:
            queryset = queryset.filter(product_id=product_id)

        return queryset

    @action(detail=False, methods=["post"], url_path="create-with-lines")
    def create_with_lines(self, request):
        serializer = FormulaCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        formula = serializer.save()

        return Response(FormulaSerializer(formula).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="activate/(?P<formula_id>[^/.]+)")
    def activate(self, request, formula_id=None):
        if not formula_id:
            return Response(
                {"error": "formula_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            formula = Formula.objects.get(id=formula_id)
        except Formula.DoesNotExist:
            return Response(
                {"error": "Formula not found"}, status=status.HTTP_404_NOT_FOUND
            )

        formula.status = "active"
        formula.save()

        return Response(
            {"message": "Formula activated successfully"}, status=status.HTTP_200_OK
        )
