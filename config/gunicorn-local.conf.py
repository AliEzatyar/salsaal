import multiprocessing

chdir = "project"
bind = "192.168.0.120:8000"
loglevel = "debug"
accesslog = "-"
errorlog = "-"
workers = 2
threads = 1
worker_class = "sync"
timeout = 60
