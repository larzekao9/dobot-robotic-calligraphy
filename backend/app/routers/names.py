from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Request
from app.ratelimit import rate_limit
from app.schemas.names import ConvertRequest, ConvertResponse
from app.services.convert import convert_name, validate_name

router = APIRouter(prefix="/api/names", tags=["names"])


@router.post("/convert", response_model=ConvertResponse, dependencies=[Depends(rate_limit)])
def convert(body: ConvertRequest, db: Annotated[Session, Depends(get_db)]) -> ConvertResponse:
    validate_name(body.name)
    data = convert_name(db, body.name)
    req = Request(
        input_name=data.input, result_json=data.model_dump(mode="json"), locale=body.locale
    )
    db.add(req)
    db.commit()
    return ConvertResponse(request_id=req.id, **data.model_dump())
