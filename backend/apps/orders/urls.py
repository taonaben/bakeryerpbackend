from rest_framework.routers import DefaultRouter

from .views import PlannedOrderViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r"planned", PlannedOrderViewSet, basename="planned_order")

urlpatterns = router.urls
