from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CompanyViewSet, WarehouseViewSet, ProductViewSet

router = DefaultRouter()
router.register(r"companies", CompanyViewSet, basename="company")
router.register(r"warehouses", WarehouseViewSet, basename="warehouse")
router.register(r"products", ProductViewSet, basename="product")

urlpatterns = [
    path("", include(router.urls)),
]
