# backend/apps/accounts/decorators.py
from functools import wraps
from django.http import JsonResponse
from .permissions import has_permission

def require_permission(module, action='read'):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not has_permission(request.user, module, action):
                return JsonResponse({'error': 'Permission denied'}, status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
