"""
Basic monitoring metrics for the application
"""

from prometheus_client import Counter, Histogram, Gauge

# Template metrics
TEMPLATE_LOAD_TIME = Histogram(
    'template_load_seconds',
    'Time spent loading templates',
    ['method', 'cache_status']
)

TEMPLATE_CACHE_HITS = Counter(
    'template_cache_hits_total',
    'Number of template cache hits'
)

TEMPLATE_CACHE_MISSES = Counter(
    'template_cache_misses_total',
    'Number of template cache misses'
)

TEMPLATE_ERRORS = Counter(
    'template_errors_total',
    'Number of template operation errors',
    ['operation']
)

ACTIVE_TEMPLATE_OPERATIONS = Gauge(
    'template_operations_active',
    'Number of active template operations'
)

# Add other common metrics as needed
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)