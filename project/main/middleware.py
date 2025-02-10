import time
from django.utils.deprecation import MiddlewareMixin
from accounts.utils import send_log_email

class RequestTimingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.start_time = time.time()

    def process_response(self, request, response):
        if hasattr(request, "start_time"):
            if request.path == "/":
                duration = time.time() - request.start_time
                send_log_email(str(duration))
                print(f"\n{request.path}Request processing time: {duration:.3f} seconds\n")
        return response
