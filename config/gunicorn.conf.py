chdir = "project"
bind = "0.0.0.0:8000"
workers = 5 # for 1 CPU
threads = 3 
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
loglevel = "info"
