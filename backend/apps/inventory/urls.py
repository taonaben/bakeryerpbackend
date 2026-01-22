from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.stock_views import StockViewSet
from .views.stock_movement_views import StockMovementViewSet
from .views.batch_views import BatchViewSet
from .views.stock_alerts_views import InventoryAlertViewSet, ProductReorderPolicyViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r"stocks", StockViewSet, basename="stock")
router.register(r"stock_movements", StockMovementViewSet, basename="stock_movement")
router.register(r"batches", BatchViewSet, basename="batch")
router.register(r"alerts", InventoryAlertViewSet, basename="inventory_alert")


urlpatterns = [
    path("", include(router.urls)),
]
