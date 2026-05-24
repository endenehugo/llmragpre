import multiprocessing


bind = "0.0.0.0:5000"

# 当前会话记忆保存在进程内，多 worker 会造成上下文漂移；
# 同时每个 worker 都会重复加载向量索引，先以单 worker 稳定运行为主。
workers = 1
threads = min(4, multiprocessing.cpu_count() or 1)
worker_class = "gthread"

# LLM 和联网工具请求可能超过 Gunicorn 默认 30 秒超时。
timeout = 180
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
capture_output = True
loglevel = "info"
preload_app = False