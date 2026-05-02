"""Router de flujo semanal."""
from typing import Optional

from fastapi import APIRouter, Depends

from core import get_current_user, require_role, new_id, iso, now_utc
from database import get_db
from models import FlujoIn

router = APIRouter(prefix="/flujo", tags=["flujo"])


@router.get("")
async def list_flujo(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    q: dict = {}
    if desde or hasta:
        q["fecha"] = {}
        if desde:
            q["fecha"]["$gte"] = desde
        if hasta:
            q["fecha"]["$lte"] = hasta
    return await db.flujo.find(q, {"_id": 0}).sort("fecha", 1).to_list(1000)


@router.post("")
async def create_flujo(body: FlujoIn, user: dict = Depends(require_role("admin", "financiero"))):
    db  = get_db()
    doc = {"id": new_id(), **body.model_dump(), "created_at": iso(now_utc())}
    await db.flujo.insert_one(doc.copy())
    return doc


@router.delete("/{fid}")
async def delete_flujo(fid: str, user: dict = Depends(require_role("admin", "financiero"))):
    db = get_db()
    await db.flujo.delete_one({"id": fid})
    return {"ok": True}
