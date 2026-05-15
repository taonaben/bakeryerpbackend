from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from .views.stock_views import StockViewSet
from .views.stock_movement_views import StockMovementViewSet
from .views.batch_views import BatchViewSet
from .views.overview_views import (
    InventoryMovementTrendsView,
    InventoryOverviewSummaryView,
)
from .views.stock_alerts_views import InventoryAlertViewSet, ProductReorderPolicyViewSet
from .views.policy_movement_views import create_movement_with_policy_view

router = DefaultRouter(trailing_slash=False)
router.register(r"stocks", StockViewSet, basename="stock")
router.register(r"stock_movements", StockMovementViewSet, basename="stock_movement")
router.register(r"batches", BatchViewSet, basename="batch")
router.register(r"alerts", InventoryAlertViewSet, basename="inventory_alert")


urlpatterns = [
    re_path(
        r"^overview/summary/?$",
        InventoryOverviewSummaryView.as_view(),
        name="inventory-overview-summary",
    ),
    re_path(
        r"^overview/movement-trends/?$",
        InventoryMovementTrendsView.as_view(),
        name="inventory-overview-movement-trends",
    ),
    path("", include(router.urls)),
    path("movements/create-with-policy", create_movement_with_policy_view, name="create_movement_with_policy"),
]
