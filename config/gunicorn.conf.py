import multiprocessing
chdir = "project"
bind = "0.0.0.0:8000"
loglevel = "debug"
accesslog = "-"
errorlog=  "-"
workers = (multiprocessing.cpu_count() * 2) + 1
threads = 2
worker_class = "sync"
timeout = 60
