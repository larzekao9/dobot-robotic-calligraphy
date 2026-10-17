import secrets
from typing import Annotated

from fastapi import Header

from app.config import settings
from app.errors import AppError


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    """Token compartido opcional (`ADMIN_TOKEN`, cabecera `X-Admin-Token`). Vacío = sin protección."""
    if not settings.admin_token:
        return
    expected = settings.admin_token.encode()
    if x_admin_token is None or not secrets.compare_digest(x_admin_token.encode(), expected):
        raise AppError("unauthorized", "Token de administrador inválido o ausente.", 401)
