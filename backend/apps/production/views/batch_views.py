from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import ProductionBatch, ProductionOrder
from ..serializers import ProductionBatchDetailSerializer, ProductionBatchSerializer


class ProductionBatchListView(APIView):
    """List all batches for a given production order."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProductionBatchSerializer
        return ProductionBatchDetailSerializer

    def get(self, request, order_id):
        order = get_object_or_404(ProductionOrder, id=order_id)
        batches = (
            ProductionBatch.objects.filter(production_order=order)
            .prefetch_related("lines", "materials", "outputs", "waste")
            .order_by("started_at")
        )
        serializer = self.get_serializer_class()(batches, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductionBatchDetailView(APIView):
    """Retrieve a single production batch with full detail."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return ProductionBatchDetailSerializer

    def get(self, request, order_id, batch_id):
        batch = get_object_or_404(
            ProductionBatch.objects.prefetch_related(
                "lines", "materials", "outputs", "waste"
            ),
            id=batch_id,
            production_order__id=order_id,
        )
        serializer = self.get_serializer_class()(batch)
        return Response(serializer.data, status=status.HTTP_200_OK)
