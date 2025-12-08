bind = "unix:myapp.sock"
workers = 3  # 核心数 * 2 + 1
worker_class = "sync"
timeout = 120
keepalive = 5
