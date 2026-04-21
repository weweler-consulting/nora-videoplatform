"""Rate limiting configuration using slowapi.

Uses X-Real-IP / X-Forwarded-For headers (set by Cloudron's reverse proxy)
so limits apply per real client IP, not the proxy's internal IP.
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_client_ip(request: Request) -> str:
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=get_client_ip)
