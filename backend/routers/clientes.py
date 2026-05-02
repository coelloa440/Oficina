"""Router de clientes."""
from fastapi import APIRouter, Depends, HTTPException

from core import get_current_user, require_role, new_id, iso, now_utc
from database import get_db
from models import ClienteIn

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.get("")
async def list_clientes(user: dict = Depends(get_current_user)):
    db = get_db()
    return await db.clientes.find({}, {"_id": 0}).to_list(500)


@router.post("")
async def create_cliente(body: ClienteIn, user: dict = Depends(require_role("admin", "financiero"))):
    db  = get_db()
    doc = {"id": new_id(), **body.model_dump(), "created_at": iso(now_utc())}
    await db.clientes.insert_one(doc.copy())
    return doc


@router.put("/{cid}")
async def update_cliente(cid: str, body: ClienteIn, user: dict = Depends(require_role("admin", "financiero"))):
    db  = get_db()
    res = await db.clientes.update_one({"id": cid}, {"$set": body.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Cliente no encontrado")
    return await db.clientes.find_one({"id": cid}, {"_id": 0})


@router.delete("/{cid}")
async def delete_cliente(cid: str, user: dict = Depends(require_role("admin"))):
    db = get_db()
    await db.clientes.delete_one({"id": cid})
    await db.facturas.delete_many({"cliente_id": cid})
    return {"ok": True}
