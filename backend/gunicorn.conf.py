import multiprocessing

# Worker settings
workers = 1  # Use only 1 worker on free tier
worker_class = 'sync'
worker_connections = 1000
timeout = 120  # Increase timeout to 120 seconds
keepalive = 5

# Memory management
max_requests = 100  # Restart worker after 100 requests
max_requests_jitter = 10

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Preload app to save memory
preload_app = True