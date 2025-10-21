from typing import Callable
from fastapi import Request, Response


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                def add(name: str, value: str):
                    headers.append((name.encode("latin-1"), value.encode("latin-1")))

                add("strict-transport-security", "max-age=31536000; includeSubDomains; preload")
                add("x-content-type-options", "nosniff")
                add("x-frame-options", "DENY")
                add("referrer-policy", "no-referrer")
                add("permissions-policy", "geolocation=(), microphone=(), camera=()")
                # Allow local + CDNs used by the demo (HTMX + Tailwind CDN)
                csp = (
                    "default-src 'self'; "
                    "img-src 'self' data:; "
                    "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
                    "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.tailwindcss.com; "
                    "connect-src 'self'"
                )
                add("content-security-policy", csp)
            await send(message)

        await self.app(scope, receive, send_wrapper)
