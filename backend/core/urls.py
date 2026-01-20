"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from apps.accounts.urls import urlpatterns as accounts_urls
from central.urls import urlpatterns as central_urls
from apps.inventory.urls import urlpatterns as inventory_urls
from health.urls import urlpatterns as health_urls

app_urlpatterns = [
    # path("auth/", include(auth_urls)),
    path("health/", include(health_urls)),
    path("account/", include(accounts_urls)),
    path("", include(central_urls)),
    path("inventory/", include(inventory_urls)),
]

third_party_urlpatterns = [
    ## JWT Auth
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    ## Schema and Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # optional ui:
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(), name="redoc"),
]


urlpatterns = [
    path("admin/", admin.site.urls),
    # Include app-specific URLs
    path("", include(app_urlpatterns)),
    # Include third-party URLs
    path("", include(third_party_urlpatterns)),
]
