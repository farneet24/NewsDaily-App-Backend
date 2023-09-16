from django.http import JsonResponse
from collections import Counter
from time import time

class SimpleRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.requests = Counter()
    
    def __call__(self, request):
        client_ip = self.get_client_ip(request)
        current_time = int(time())
        
        # Clean up old request data
        to_delete = [k for k, v in self.requests.items() if current_time - k > 60]
        for k in to_delete:
            del self.requests[k]
        
        # Check rate limits
        self.requests[current_time] += 1
        if sum(self.requests.values()) > 10:  # 5 requests per minute
            return JsonResponse({'error': 'Rate limit exceeded'}, status=429)
        
        return self.get_response(request)
    
    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
