"""A bounded installation-wide throttle for loopback staging, not public auth."""
import time

from django.contrib.auth.views import LoginView
from django.db import DatabaseError, transaction
from django.http import HttpResponse

from .models import LoginBudget

WINDOW_SECONDS = 60
MAX_ATTEMPTS = 10


def reserve_attempt(now=None):
    """Reserve a slot before authentication. All login attempts count.

    No usernames, addresses, passwords or per-client keys are stored.
    SQLite IMMEDIATE transactions serialize reservations across processes.
    """
    now = int(time.time()) if now is None else now
    if type(now) is not int or now < 0:
        raise ValueError("Invalid time")
    with transaction.atomic():
        budget, _ = LoginBudget.objects.get_or_create(
            pk=1, defaults={"window_start": now, "attempts": 0})
        elapsed = now - budget.window_start
        if elapsed < 0:
            # Do not allow clock rollback to reset a filled budget.
            return WINDOW_SECONDS
        if elapsed >= WINDOW_SECONDS:
            budget.window_start = now
            budget.attempts = 0
            elapsed = 0
        if budget.attempts >= MAX_ATTEMPTS:
            return WINDOW_SECONDS - elapsed
        budget.attempts += 1
        budget.save(update_fields=["window_start", "attempts"])
        return 0


class LocalLoginView(LoginView):
    """Use Django's own authentication and inherited CSRF-protected dispatch."""

    def post(self, request, *args, **kwargs):
        try:
            retry = reserve_attempt()
        except (DatabaseError, ValueError):
            return HttpResponse("Local sign-in temporarily unavailable.", status=503)
        if retry:
            response = HttpResponse("Local sign-in attempt limit reached. Try again later.", status=429)
            response["Retry-After"] = str(retry)
            return response
        return super().post(request, *args, **kwargs)
