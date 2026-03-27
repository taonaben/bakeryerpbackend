from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from ..models import ProductionOrder

from ..serializers import (
    ProductionPlanSerializer,
)
from ..services.production_planner import ProductionPlanner


class ProductionPlanAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        order = get_object_or_404(ProductionOrder, id=order_id)

        try:
            plan = ProductionPlanner.plan(order)
        except DjangoValidationError as exc:
            return Response(
                {"errors": exc.message_dict or exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProductionPlanSerializer(plan)
        return Response(serializer.data)
