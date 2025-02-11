from functools import wraps
from time import perf_counter
from django.db import connection, reset_queries
from accounts.utils import send_log_email
from django.conf import settings


def query_execution_time(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        # reseting previous queries
        reset_queries()

        # start queries
        start_queries = len(connection.queries)
        start_time = perf_counter()
        result = func(*args, **kwargs)
        for q in connection.queries:
            print(q, "\n\n")
        end_time = perf_counter()

        # end queries
        end_queries = len(connection.queries)

        total_time = f"{end_time - start_time} % 0.4f"
        total_queries = end_queries - start_queries
        print(total_queries, "queries | ", total_time, "total time.")
        if not settings.LOCAL:
            send_log_email(str(total_time), type_="db")
        return result

    return wrapper
