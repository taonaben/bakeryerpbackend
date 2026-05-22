from django.urls import path
from .views import DashboardLayoutView, WidgetRegistryView

urlpatterns = [
    path("layout/", DashboardLayoutView.as_view(), name="dashboard-layout"),
    path("widgets/", WidgetRegistryView.as_view(), name="dashboard-widgets"),
]
