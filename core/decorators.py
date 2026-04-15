import json
import logging
from functools import wraps
from django.http import JsonResponse
from .models import get_current_tenant

logger = logging.getLogger(__name__)


def tenant_api(methods=None, parse_json=False):
    """
    Decorator that handles common API boilerplate:
    - Validates tenant context exists
    - Optionally restricts HTTP methods
    - Optionally parses JSON request body
    - Wraps handler in try/except with logging

    Usage:
        @login_required
        @tenant_api(methods=['POST'], parse_json=True)
        def my_api(request, tenant, data):
            ...
            return JsonResponse({'success': True})

        @login_required
        @tenant_api()
        def my_api(request, tenant):
            ...
            return JsonResponse({'success': True, 'items': items})
    """
    if methods:
        methods = [m.upper() for m in methods]

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if methods and request.method not in methods:
                return JsonResponse({'error': f'{request.method} not allowed'}, status=405)

            tenant = get_current_tenant()
            if not tenant:
                return JsonResponse({'error': 'No tenant context'}, status=400)

            try:
                if parse_json and request.method in ('POST', 'PUT', 'PATCH'):
                    data = json.loads(request.body) if request.body else {}
                    return view_func(request, tenant, data, *args, **kwargs)
                else:
                    return view_func(request, tenant, *args, **kwargs)
            except Exception as e:
                logger.error(f"{view_func.__name__} error: {e}", exc_info=True)
                return JsonResponse({'error': str(e)}, status=500)

        return wrapper
    return decorator
