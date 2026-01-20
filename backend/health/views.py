import os
import platform
import django
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Comprehensive health check endpoint for the Bakery ERP backend.
    
    Returns system status, version information, and database connectivity.
    
    Response includes:
        - status: Overall system health
        - version: Application version
        - environment: Current environment details
        - database: Database connection status
        - system: System information
        - url: Current request URL
    """
    
    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Build response data
    health_data = {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "timestamp": django.utils.timezone.now().isoformat(),
        "version": getattr(settings, 'VERSION', '1.0.0'),
        "environment": {
            "debug": settings.DEBUG,
            "allowed_hosts": settings.ALLOWED_HOSTS,
            "django_version": django.get_version(),
            "python_version": platform.python_version(),
        },
        "database": {
            "status": db_status,
            "engine": settings.DATABASES['default']['ENGINE'],
            "name": settings.DATABASES['default']['NAME'],
        },
        "system": {
            "platform": platform.system(),
            "architecture": platform.architecture()[0],
            "hostname": platform.node(),
        },
        "url": request.build_absolute_uri(),
    }
    
    response_status = status.HTTP_200_OK if db_status == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return Response(health_data, status=response_status)