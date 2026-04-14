from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FormulaViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r"formulas", FormulaViewSet, basename="formula")

urlpatterns = [
    path("", include(router.urls)),
]