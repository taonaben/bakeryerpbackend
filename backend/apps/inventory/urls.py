from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StockMovementViewSet, BatchViewSet, StockViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r"stocks", StockViewSet, basename="stock")
router.register(r"stock_movements", StockMovementViewSet, basename="stock_movement")
router.register(r"batches", BatchViewSet, basename="batch")

urlpatterns = [
    path("", include(router.urls)),
]
