import multiprocessing
import os

user = os.environ.get("USER")

# Gunicorn configuration file
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
keepalive = 2
timeout = 120
capture_output = True
enable_stdio_inheritance = True

# Logging
project_folder = os.path.dirname(os.path.abspath(__file__))
accesslog = os.path.join(project_folder, "logs/gunicorn_access.log")
errorlog = os.path.join(project_folder, "logs/gunicorn_error.log")
loglevel = "debug"

# Development settings
reload = True  # Auto-reload on code changes

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Worker process name
proc_name = "lumina"

# Maximum requests a worker will process before restarting
max_requests = 1000
max_requests_jitter = 50

# Preload app (recommended for better performance)
preload_app = True

def on_starting(server):
    server.log.info("Starting Lumina server")

def on_exit(server):
    server.log.info("Stopping Lumina server")

def post_worker_init(worker):
    worker.log.info(f"Worker initialized")
