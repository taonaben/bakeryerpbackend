from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CompanyViewSet, WarehouseViewSet, ProductViewSet
from apps.inventory.views.stock_alerts_views import ProductReorderPolicyViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r"companies", CompanyViewSet, basename="company")
router.register(r"warehouses", WarehouseViewSet, basename="warehouse")
router.register(r"products", ProductViewSet, basename="product")
router.register(
    r"reorder_policies",
    ProductReorderPolicyViewSet,
    basename="product_reorder_policy",
)


urlpatterns = [
    path("", include(router.urls)),
]
