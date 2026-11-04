import multiprocessing

bind = "unix:/srv/guda/run/gunicorn.sock"
workers = max(3, multiprocessing.cpu_count() * 2 + 1)
worker_class = "sync"
timeout = 60
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
loglevel = "info"
forwarded_allow_ips = "127.0.0.1"
