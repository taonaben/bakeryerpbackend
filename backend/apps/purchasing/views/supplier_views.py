from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.purchasing.serializers.supplier_serializers import (
    SupplierCreateUpdateSerializer,
    SupplierProductCreateSerializer,
    SupplierProductSerializer,
    SupplierSerializer,
)
from apps.purchasing.services.supplier_services import (
    add_product_to_catalogue,
    create_supplier,
    deactivate_supplier,
    get_preferred_supplier,
    reactivate_supplier,
    update_supplier,
)


class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer

    def get_queryset(self):
        from apps.purchasing.models import Supplier

        qs = Supplier.objects.select_related("company").all()
        company_id = self.request.query_params.get(
            "company_id", getattr(self.request.user, "company_id", None)
        )
        if company_id:
            qs = qs.filter(company_id=company_id)
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")
        return qs

    def create(self, request, *args, **kwargs):
        serializer = SupplierCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            supplier = create_supplier(serializer.validated_data)
        except DjangoValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            SupplierSerializer(supplier).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        serializer = SupplierCreateUpdateSerializer(
            data=request.data, partial=kwargs.get("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        try:
            supplier = update_supplier(self.kwargs["pk"], serializer.validated_data)
        except DjangoValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SupplierSerializer(supplier).data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        try:
            supplier = deactivate_supplier(self.kwargs["pk"])
        except DjangoValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SupplierSerializer(supplier).data)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        try:
            supplier = reactivate_supplier(pk)
        except DjangoValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SupplierSerializer(supplier).data)

    @action(detail=True, methods=["post"], url_path="add-product")
    def add_product(self, request, pk=None):
        serializer = SupplierProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            sp = add_product_to_catalogue(
                supplier_id=pk,
                product_id=data["product_id"],
                price=data["price"],
                lead_time_days=data["lead_time_days"],
                is_preferred=data.get("is_preferred", False),
            )
        except DjangoValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            SupplierProductSerializer(sp).data, status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["get"], url_path="preferred-supplier")
    def preferred_supplier(self, request):
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response(
                {"detail": "product_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        company_id = request.query_params.get("company_id")
        sp = get_preferred_supplier(product_id, company_id=company_id)
        if not sp:
            return Response(
                {"detail": "No preferred supplier found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(SupplierProductSerializer(sp).data)
