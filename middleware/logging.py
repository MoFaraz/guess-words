import logging
import time
import json
from django.http import HttpRequest, HttpResponse

# Get a dedicated logger for API access logs
logger = logging.getLogger('api.access')


class RequestLoggingMiddleware:
    """
    Middleware to log API requests including method, path, status code, and response time.
    Logs are written to a file for better analysis and record-keeping.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Record start time
        start_time = time.time()

        # Process the request
        response = self.get_response(request)

        # Calculate duration
        duration = time.time() - start_time

        # Skip logging for static files and admin panel
        if not self._should_log_request(request.path):
            return response

        # Prepare log data
        log_data = {
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration_ms': round(duration * 1000, 2),  # Convert to ms
            'user': str(request.user) if request.user.is_authenticated else 'anonymous',
            'ip': self._get_client_ip(request),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        }

        # Log the request as JSON
        logger.info(json.dumps(log_data))

        return response

    def _should_log_request(self, path: str) -> bool:
        """
        Determine if a request should be logged based on path.
        Skip static files, admin panel, etc.
        """
        skip_prefixes = ['/static/', '/media/', '/admin/jsi18n/']
        skip_extensions = ['.js', '.css', '.ico', '.jpg', '.png', '.svg']

        for prefix in skip_prefixes:
            if path.startswith(prefix):
                return False

        for ext in skip_extensions:
            if path.endswith(ext):
                return False

        return True

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip