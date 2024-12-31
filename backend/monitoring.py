from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time
from functools import wraps
import psutil
import logging
from config import settings

# Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint']
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'Number of active HTTP requests'
)

VIDEO_PROCESSING_DURATION = Histogram(
    'video_processing_duration_seconds',
    'Video processing duration in seconds'
)

VIDEO_UPLOAD_SIZE = Histogram(
    'video_upload_size_bytes',
    'Size of uploaded videos in bytes'
)

CELERY_TASKS_ACTIVE = Gauge(
    'celery_tasks_active',
    'Number of active Celery tasks'
)

SYSTEM_MEMORY_USAGE = Gauge(
    'system_memory_usage_bytes',
    'System memory usage in bytes'
)

SYSTEM_CPU_USAGE = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

def track_request_metrics():
    """Request metrics decorator"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            method = args[0].method
            endpoint = args[0].url.path
            
            ACTIVE_REQUESTS.inc()
            start_time = time.time()
            
            try:
                response = await func(*args, **kwargs)
                status = response.status_code
                return response
            except Exception as e:
                status = 500
                raise e
            finally:
                duration = time.time() - start_time
                REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
                REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
                ACTIVE_REQUESTS.dec()
        
        return wrapper
    return decorator

def track_video_processing(func):
    """Video processing metrics decorator"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            VIDEO_PROCESSING_DURATION.observe(duration)
            return result
        except Exception as e:
            raise e
    return wrapper

def update_system_metrics():
    """Sistem metriklerini güncelle"""
    while True:
        try:
            # Memory kullanımı
            memory = psutil.virtual_memory()
            SYSTEM_MEMORY_USAGE.set(memory.used)
            
            # CPU kullanımı
            cpu_percent = psutil.cpu_percent(interval=1)
            SYSTEM_CPU_USAGE.set(cpu_percent)
            
            # Celery task sayısı
            # Bu kısım Celery API'sine göre güncellenebilir
            
            time.sleep(5)  # 5 saniyede bir güncelle
        except Exception as e:
            logging.error(f"Metric update error: {str(e)}")

def start_metrics_server():
    """Prometheus metrics server'ı başlat"""
    try:
        start_http_server(settings.METRICS_PORT)
        logging.info(f"Metrics server started on port {settings.METRICS_PORT}")
    except Exception as e:
        logging.error(f"Metrics server start failed: {str(e)}")

# Monitoring başlat
if settings.ENABLE_METRICS:
    start_metrics_server() 