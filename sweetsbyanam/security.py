"""Small security helpers: rate limiting, CSRF tokens and response headers."""
import hmac
import secrets
import time
from collections import defaultdict, deque

from flask import abort, request, session


class RateLimiter:
    """Allow at most `limit` events per `window` seconds for each key (kept in memory)."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit, self.window = limit, window
        self._events: dict[str, deque] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque:
        events = self._events[key]
        while events and now - events[0] > self.window:
            events.popleft()
        if not events:
            self._events.pop(key, None)
            return self._events[key]
        return events

    def blocked(self, key: str) -> bool:
        return len(self._prune(key, time.monotonic())) >= self.limit

    def hit(self, key: str) -> None:
        now = time.monotonic()
        self._prune(key, now).append(now)

    def retry_after(self, key: str) -> int:
        events = self._events.get(key)
        return int(self.window - (time.monotonic() - events[0])) + 1 if events else 0

    def clear(self, key: str) -> None:
        self._events.pop(key, None)


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def require_csrf() -> None:
    sent = request.form.get("csrf_token", "")
    if not sent or not hmac.compare_digest(sent, session.get("csrf", "")):
        abort(400, "Your session expired. Please go back, refresh the page and try again.")


CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; script-src 'self'; form-action 'self'; frame-ancestors 'none'; "
       "base-uri 'self'")


def add_security_headers(response):
    response.headers.setdefault("Content-Security-Policy", CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response
