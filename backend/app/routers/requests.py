import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import Request
from app.schemas.names import ConvertResponse

router = APIRouter(prefix="/api/requests", tags=["requests"])


class RequestItem(BaseModel):
    id: uuid.UUID
    input_name: str
    created_at: str
    locale: str
    zh_text: str | None
    ja_text: str | None


class RequestPage(BaseModel):
    items: list[RequestItem]
    total: int
    page: int
    page_size: int


def _first(result: dict[str, list[dict[str, str]]], script: str) -> str | None:
    options = result.get(script) or []
    return options[0]["text"] if options else None


@router.get("")
def list_requests(
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=60)] = None,
) -> RequestPage:
    stmt = select(Request)
    if q:
        stmt = stmt.where(Request.input_name.ilike(f"%{q.strip()}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Request.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    items = [
        RequestItem(
            id=r.id,
            input_name=r.input_name,
            created_at=r.created_at.isoformat(),
            locale=r.locale,
            zh_text=_first(r.result_json, "zh"),
            ja_text=_first(r.result_json, "ja"),
        )
        for r in rows
    ]
    return RequestPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{request_id}")
def get_request(request_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> ConvertResponse:
    req = db.get(Request, request_id)
    if req is None:
        raise AppError("request_not_found", "No existe esa consulta.", 404)
    return ConvertResponse(request_id=req.id, **req.result_json)
