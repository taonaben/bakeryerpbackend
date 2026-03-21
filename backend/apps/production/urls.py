from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ProductionPlanAPIView, ProductionOrderViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r"orders", ProductionOrderViewSet, basename="production_order")

urlpatterns = [
    path(
        "orders/<uuid:order_id>/plan",
        ProductionPlanAPIView.as_view(),
        name="production_order_plan",
    ),
] + router.urls
