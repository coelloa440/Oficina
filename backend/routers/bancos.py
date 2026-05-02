"""Router de bancos."""
from fastapi import APIRouter, Depends, HTTPException

from core import get_current_user, require_role, new_id, iso, now_utc
from database import get_db
from models import BankIn

router = APIRouter(prefix="/bancos", tags=["bancos"])


def _add_disponible(b: dict) -> dict:
    b["disponible"] = round(
        b["saldo_efectivo"] + b["sobregiro_asignado"] - b["sobregiro_utilizado"], 2
    )
    return b


@router.get("")
async def list_bancos(user: dict = Depends(get_current_user)):
    db    = get_db()
    items = await db.bancos.find({}, {"_id": 0}).to_list(200)
    return [_add_disponible(b) for b in items]


@router.post("")
async def create_banco(body: BankIn, user: dict = Depends(require_role("admin", "financiero"))):
    db  = get_db()
    doc = {"id": new_id(), **body.model_dump(), "created_at": iso(now_utc())}
    await db.bancos.insert_one(doc.copy())
    return _add_disponible(doc)


@router.put("/{banco_id}")
async def update_banco(banco_id: str, body: BankIn, user: dict = Depends(require_role("admin", "financiero"))):
    db  = get_db()
    res = await db.bancos.update_one({"id": banco_id}, {"$set": body.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Banco no encontrado")
    doc = await db.bancos.find_one({"id": banco_id}, {"_id": 0})
    return _add_disponible(doc)


@router.delete("/{banco_id}")
async def delete_banco(banco_id: str, force: bool = False, user: dict = Depends(require_role("admin"))):
    db            = get_db()
    cheques_count = await db.cheques.count_documents({"banco_id": banco_id})
    flujo_count   = await db.flujo.count_documents({"banco_id": banco_id})
    if (cheques_count > 0 or flujo_count > 0) and not force:
        raise HTTPException(
            status_code=409,
            detail=f"El banco tiene {cheques_count} cheque(s) y {flujo_count} movimiento(s) vinculados. Usa ?force=true para eliminar en cascada.",
        )
    if force:
        await db.cheques.delete_many({"banco_id": banco_id})
        await db.flujo.delete_many({"banco_id": banco_id})
    res = await db.bancos.delete_one({"id": banco_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Banco no encontrado")
    return {
        "ok": True,
        "cheques_eliminados": cheques_count if force else 0,
        "flujo_eliminados":   flujo_count   if force else 0,
    }
