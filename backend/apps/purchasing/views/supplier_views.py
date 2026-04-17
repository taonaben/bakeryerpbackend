from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.purchasing.models import Supplier, SupplierContact, SupplierDocument
from apps.purchasing.serializers.supplier_serializers import (
    SupplierContactCreateSerializer,
    SupplierContactSerializer,
    SupplierCreateUpdateSerializer,
    SupplierDocumentCreateSerializer,
    SupplierDocumentSerializer,
    SupplierProductCreateSerializer,
    SupplierProductSerializer,
    SupplierPutOnHoldSerializer,
    SupplierSerializer,
)
from apps.purchasing.services.supplier_services import (
    add_product_to_catalogue,
    create_supplier,
    create_supplier_contact,
    create_supplier_document,
    deactivate_supplier,
    get_preferred_supplier,
    put_supplier_on_hold,
    reactivate_supplier,
    release_supplier_hold,
    update_supplier,
)
from core.mixins import CompanyScopedMixin


class SupplierViewSet(CompanyScopedMixin, viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    queryset = Supplier.objects.select_related("company").all()
    company_field = "company"

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SupplierCreateUpdateSerializer
        if self.action == "add_product":
            return SupplierProductCreateSerializer
        if self.action == "preferred_supplier":
            return SupplierProductSerializer
        if self.action == "put_on_hold":
            return SupplierPutOnHoldSerializer
        return SupplierSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            supplier = create_supplier(serializer.validated_data)
        except DjangoValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            SupplierSerializer(supplier).data, status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(
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
        serializer = self.get_serializer(data=request.data)
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

    @action(detail=True, methods=["post"], url_path="put-on-hold")
    def put_on_hold(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")
        try:
            supplier = put_supplier_on_hold(pk, reason)
        except DjangoValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SupplierSerializer(supplier).data)

    @action(detail=True, methods=["post"], url_path="release-hold")
    def release_hold(self, request, pk=None):
        try:
            supplier = release_supplier_hold(pk)
        except DjangoValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SupplierSerializer(supplier).data)


class SupplierContactViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierContactSerializer

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SupplierContactCreateSerializer
        return SupplierContactSerializer

    def get_queryset(self):
        return SupplierContact.objects.filter(
            supplier_id=self.kwargs["supplier_pk"]
        ).order_by("-is_primary", "name")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("supplier", None)  # supplier comes from the URL
        try:
            contact = create_supplier_contact(self.kwargs["supplier_pk"], data)
        except DjangoValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            SupplierContactSerializer(contact).data, status=status.HTTP_201_CREATED
        )


class SupplierDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierDocumentSerializer

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SupplierDocumentCreateSerializer
        return SupplierDocumentSerializer

    def get_queryset(self):
        return SupplierDocument.objects.filter(
            supplier_id=self.kwargs["supplier_pk"]
        ).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("supplier", None)  # supplier comes from the URL
        try:
            doc = create_supplier_document(self.kwargs["supplier_pk"], data)
        except DjangoValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            SupplierDocumentSerializer(doc).data, status=status.HTTP_201_CREATED
        )
