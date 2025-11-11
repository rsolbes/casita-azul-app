import multiprocessing
import os

# Worker settings - Optimized for Render free tier
workers = int(os.getenv('WEB_CONCURRENCY', 1))  # Keep 1 worker for free tier
worker_class = 'sync'
worker_connections = 1000
timeout = 300  # 5 minutes - critical for slow database connections
keepalive = 5
graceful_timeout = 30

# Memory management
max_requests = 200  # Restart worker after 200 requests
max_requests_jitter = 20

# Bind settings
bind = '0.0.0.0:10000'  # Render uses port 10000

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
capture_output = True
enable_stdio_inheritance = True

# Preload app to save memory and initialize connections early
preload_app = True

# Startup hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    print("🚀 Starting Gunicorn server...")
    print(f"⚙️  Workers: {workers}")
    print(f"⏱️  Timeout: {timeout}s")

def when_ready(server):
    """Called just after the server is started."""
    print("✅ Gunicorn server is ready and listening!")
    print(f"🌐 Listening on: {bind}")

def on_exit(server):
    """Called just before the master process exits."""
    print("👋 Shutting down Gunicorn server...")