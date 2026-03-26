from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ProductionPlanAPIView,
    ProductionOrderViewSet,
    ProductionStartAPIView,
    ProductionFinishAPIView,
    ReworkOrderViewSet,
    ReworkStartAPIView,
    ReworkFinishAPIView,
)

router = DefaultRouter(trailing_slash=False)
router.register(r"orders", ProductionOrderViewSet, basename="production_order")
router.register(r"rework", ReworkOrderViewSet, basename="rework_order")

urlpatterns = [
    path(
        "orders/<uuid:order_id>/plan",
        ProductionPlanAPIView.as_view(),
        name="production_order_plan",
    ),
    path(
        "orders/<uuid:order_id>/start",
        ProductionStartAPIView.as_view(),
        name="production_order_start",
    ),
    path(
        "orders/<uuid:order_id>/finish",
        ProductionFinishAPIView.as_view(),
        name="production_order_finish",
    ),
    path(
        "rework/<uuid:order_id>/start",
        ReworkStartAPIView.as_view(),
        name="rework_order_start",
    ),
    path(
        "rework/<uuid:order_id>/finish",
        ReworkFinishAPIView.as_view(),
        name="rework_order_finish",
    ),
] + router.urls
