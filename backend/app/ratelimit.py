import time
from collections import defaultdict, deque

from fastapi import Request

from app.config import settings
from app.errors import AppError

_WINDOW_SECONDS = 60.0
_hits: defaultdict[str, deque[float]] = defaultdict(deque)


def reset() -> None:
    _hits.clear()


def rate_limit(request: Request) -> None:
    """Ventana deslizante de 60 s por IP, en memoria (suficiente para un stand con una tablet)."""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    hits = _hits[ip]
    while hits and now - hits[0] > _WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= settings.rate_limit_per_minute:
        raise AppError(
            "rate_limited", "Demasiadas solicitudes. Intenta de nuevo en un minuto.", 429
        )
    hits.append(now)
