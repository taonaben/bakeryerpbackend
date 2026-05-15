from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import CompanyScopedMixin

from .models import Formula
from .serializers import (
    FormulaHoldSerializer,
    FormulaSerializer,
    FormulaWriteSerializer,
)
from .services.formula_services import FormulaService


class FormulaViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = FormulaSerializer
    permission_classes = [IsAuthenticated]
    queryset = Formula.objects.select_related("product").prefetch_related(
        "lines", "lines__product"
    )

    ordering_fields = ["created_at", "product__name", "revision"]
    search_fields = ["name", "product__name", "revision"]
    company_field = "product__company"
    tags = ["Formulas"]

    @staticmethod
    def _validation_error_response(exc):
        detail = (
            getattr(exc, "message_dict", None)
            or getattr(exc, "messages", None)
            or [str(exc)]
        )
        return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update", "create_with_lines"):
            return FormulaWriteSerializer
        if self.action == "put_on_hold":
            return FormulaHoldSerializer
        return FormulaSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        product_id = self.request.query_params.get("product_id")
        status_value = self.request.query_params.get("status")
        is_active = self.request.query_params.get("is_active")
        on_hold = self.request.query_params.get("on_hold")

        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")
        if on_hold is not None:
            queryset = queryset.filter(on_hold=on_hold.lower() == "true")

        return queryset.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        formula = serializer.save()
        return Response(FormulaSerializer(formula).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        formula = self.get_object()
        partial = kwargs.get("partial", False)
        serializer = self.get_serializer(
            formula,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)

        if formula.status == "draft":
            formula = serializer.save()
        else:
            formula = FormulaService.revise_with_lines(
                formula,
                serializer.validated_data,
                replace_lines=not partial,
            )

        return Response(FormulaSerializer(formula).data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        try:
            if self.get_object().status == "draft":
                return super().destroy(request, *args, **kwargs)
            formula = FormulaService.deactivate_formula(self.get_object())
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)
        return Response(FormulaSerializer(formula).data)

    @action(detail=False, methods=["post"], url_path="create-with-lines")
    def create_with_lines(self, request):
        return self.create(request)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        try:
            formula = FormulaService.activate_formula(self.get_object())
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)
        return Response(FormulaSerializer(formula).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            formula = FormulaService.deactivate_formula(self.get_object())
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)
        return Response(FormulaSerializer(formula).data)

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        try:
            formula = FormulaService.archive_formula(self.get_object())
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)
        return Response(FormulaSerializer(formula).data)

    @action(detail=True, methods=["post"], url_path="put-on-hold")
    def put_on_hold(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            formula = FormulaService.put_formula_on_hold(
                self.get_object(),
                reason=serializer.validated_data.get("reason", ""),
            )
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)
        return Response(FormulaSerializer(formula).data)

    @action(detail=True, methods=["post"], url_path="release-hold")
    def release_hold(self, request, pk=None):
        try:
            formula = FormulaService.release_formula_hold(self.get_object())
        except DjangoValidationError as exc:
            return self._validation_error_response(exc)
        return Response(FormulaSerializer(formula).data)
