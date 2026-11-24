"""Keep staging responses private and limited to local resources."""
from django.http import HttpResponseForbidden


class LocalHeaders:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Never trust forwarding headers or make this a public service.
        request.get_host()
        if request.META.get('REMOTE_ADDR') not in ('127.0.0.1', '::1'):
            response = HttpResponseForbidden('Local staging only')
        else:
            response = self.get_response(request)
        response["Cache-Control"] = "no-store"
        response["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response
