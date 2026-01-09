from django.urls import path, include
from rest_framework.routers import DefaultRouter
import apps.accounts.views as views

router = DefaultRouter()
router.register(r"", views.UserViewSet, basename="user")

urlpatterns = [
    path("", include(router.urls)),
    path("login/", views.LoginView.as_view(), name="login_user"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
]
