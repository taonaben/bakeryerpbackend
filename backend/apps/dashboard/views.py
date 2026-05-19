from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import DashboardWidget
from .serializers import DashboardWidgetSerializer, LayoutSaveSerializer
from .widgets import WIDGET_REGISTRY, DEFAULT_LAYOUT


class WidgetRegistryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List available widgets",
        description="Returns the full widget registry — all infolets the frontend can offer the user.",
        responses={200: OpenApiResponse(description="Widget registry dict keyed by widget_key.")},
    )
    def get(self, request):
        return Response(WIDGET_REGISTRY)


class DashboardLayoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get user dashboard layout",
        description="Returns the saved widget layout for the authenticated user. Falls back to the default layout if none is saved.",
        responses={200: DashboardWidgetSerializer(many=True)},
    )
    def get(self, request):
        widgets = DashboardWidget.objects.filter(user=request.user)
        if not widgets.exists():
            return Response(DEFAULT_LAYOUT)
        return Response(DashboardWidgetSerializer(widgets, many=True).data)

    @extend_schema(
        summary="Save user dashboard layout",
        description="Replaces the user's entire layout in one shot. Send the full array of widget objects.",
        request=LayoutSaveSerializer,
        responses={200: DashboardWidgetSerializer(many=True)},
    )
    def put(self, request):
        serializer = LayoutSaveSerializer(data={"layout": request.data})
        serializer.is_valid(raise_exception=True)
        layout = serializer.validated_data["layout"]

        DashboardWidget.objects.filter(user=request.user).delete()
        DashboardWidget.objects.bulk_create(
            [DashboardWidget(user=request.user, **item) for item in layout]
        )

        saved = DashboardWidget.objects.filter(user=request.user)
        return Response(DashboardWidgetSerializer(saved, many=True).data)
