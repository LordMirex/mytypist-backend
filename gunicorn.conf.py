"""
Production Gunicorn configuration for MyTypist Backend
"""

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = int(os.getenv("WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Performance
keepalive = 5
preload_app = True
worker_tmp_dir = "/dev/shm"  # Use RAM for temporary files

# Timeouts
timeout = 30
keepalive_timeout = 5
graceful_timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "mytypist-backend"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance optimizations
def when_ready(server):
    """Called when the server is ready"""
    print("🚀 MyTypist Backend ready for production traffic")

def worker_int(worker):
    """Called when a worker receives the SIGINT or SIGQUIT signal"""
    print(f"⚠️ Worker {worker.pid} received shutdown signal")

def pre_fork(server, worker):
    """Called just before a worker is forked"""
    print(f"🔄 Forking worker {worker.pid}")

def post_fork(server, worker):
    """Called after a worker is forked"""
    # Initialize uvloop for better performance
    try:
        import uvloop
        uvloop.install()
        print(f"✅ uvloop enabled for worker {worker.pid}")
    except ImportError:
        print(f"⚠️ uvloop not available for worker {worker.pid}")

# Environment-specific overrides
if os.getenv("ENVIRONMENT") == "production":
    workers = max(4, multiprocessing.cpu_count())
    max_requests = 2000
    timeout = 120
elif os.getenv("ENVIRONMENT") == "development":
    workers = 1
    reload = True
    timeout = 300