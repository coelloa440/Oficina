"""Router de cheques."""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from core import get_current_user, require_role, new_id, iso, now_utc
from database import get_db
from models import ChequeIn

router = APIRouter(prefix="/cheques", tags=["cheques"])


def _enrich(ch: dict) -> dict:
    try:
        d = datetime.fromisoformat(ch["fecha_cobro"]).date()
        ch["dias_restantes"] = (d - date.today()).days
    except Exception:
        ch["dias_restantes"] = None
    return ch


@router.get("")
async def list_cheques(estado: Optional[str] = None, user: dict = Depends(get_current_user)):
    db = get_db()
    q  = {}
    if estado:
        q["estado"] = estado
    items  = await db.cheques.find(q, {"_id": 0}).sort("fecha_cobro", 1).to_list(1000)
    bancos = {b["id"]: b["nombre"] for b in await db.bancos.find({}, {"_id": 0}).to_list(200)}
    result = []
    for c in items:
        c = _enrich(c)
        c["banco_nombre"] = bancos.get(c.get("banco_id"), "—")
        result.append(c)
    return result


@router.post("")
async def create_cheque(body: ChequeIn, user: dict = Depends(require_role("admin", "financiero"))):
    db  = get_db()
    doc = {"id": new_id(), **body.model_dump(), "created_at": iso(now_utc())}
    await db.cheques.insert_one(doc.copy())
    if doc["estado"] == "cobrado":
        await db.bancos.update_one({"id": doc["banco_id"]}, {"$inc": {"saldo_efectivo": -doc["valor"]}})
    return _enrich(doc)


@router.put("/{cid}")
async def update_cheque(cid: str, body: ChequeIn, user: dict = Depends(require_role("admin", "financiero"))):
    db   = get_db()
    prev = await db.cheques.find_one({"id": cid}, {"_id": 0})
    if not prev:
        raise HTTPException(404, "Cheque no encontrado")
    await db.cheques.update_one({"id": cid}, {"$set": body.model_dump()})
    new  = await db.cheques.find_one({"id": cid}, {"_id": 0})
    # Transición a cobrado → descontar
    if prev["estado"] != "cobrado" and new["estado"] == "cobrado":
        await db.bancos.update_one({"id": new["banco_id"]}, {"$inc": {"saldo_efectivo": -new["valor"]}})
    # Revertir cobrado → otro estado → reponer
    if prev["estado"] == "cobrado" and new["estado"] != "cobrado":
        await db.bancos.update_one({"id": prev["banco_id"]}, {"$inc": {"saldo_efectivo": prev["valor"]}})
    return _enrich(new)


@router.delete("/{cid}")
async def delete_cheque(cid: str, user: dict = Depends(require_role("admin"))):
    db = get_db()
    await db.cheques.delete_one({"id": cid})
    return {"ok": True}
