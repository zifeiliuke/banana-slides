import os

# Gunicorn config for production

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5000")

# 6c machine baseline:
# - web is mostly I/O (DB + upstream AI task creation), so threads are useful
# - keep workers modest to avoid connection explosion to MySQL
workers = int(os.getenv("GUNICORN_WORKERS", "4"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")

timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "2000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "200"))

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

