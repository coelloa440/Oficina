"""Router de facturas (cartera) y retenciones."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from core import get_current_user, require_role, new_id, iso, now_utc
from database import get_db
from models import FacturaIn

router = APIRouter(tags=["facturas"])


# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────

def _total(f: dict) -> dict:
    f["total"] = round(f["subtotal"] - f["anticipos"] - f["retencion"], 2)
    return f


# ──────────────────────────────────────────────
# Facturas / Cartera
# ──────────────────────────────────────────────

@router.get("/facturas")
async def list_facturas(
    cliente_id: Optional[str] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    q: dict = {}
    if cliente_id:
        q["cliente_id"] = cliente_id
    if desde or hasta:
        q["fecha_emision"] = {}
        if desde:
            q["fecha_emision"]["$gte"] = desde
        if hasta:
            q["fecha_emision"]["$lte"] = hasta
    items = await db.facturas.find(q, {"_id": 0}).sort("fecha_emision", -1).to_list(1000)
    return [_total(f) for f in items]


@router.post("/facturas")
async def create_factura(body: FacturaIn, user: dict = Depends(require_role("admin", "financiero"))):
    db  = get_db()
    doc = {"id": new_id(), **body.model_dump(), "created_at": iso(now_utc())}
    await db.facturas.insert_one(doc.copy())
    return _total(doc)


@router.put("/facturas/{fid}")
async def update_factura(fid: str, body: FacturaIn, user: dict = Depends(require_role("admin", "financiero"))):
    db  = get_db()
    res = await db.facturas.update_one({"id": fid}, {"$set": body.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Factura no encontrada")
    doc = await db.facturas.find_one({"id": fid}, {"_id": 0})
    return _total(doc)


@router.delete("/facturas/{fid}")
async def delete_factura(fid: str, user: dict = Depends(require_role("admin"))):
    db = get_db()
    await db.facturas.delete_one({"id": fid})
    return {"ok": True}


# ──────────────────────────────────────────────
# Retenciones (vista derivada de facturas)
# ──────────────────────────────────────────────

@router.get("/retenciones")
async def list_retenciones(
    cliente_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    q: dict = {"retencion": {"$gt": 0}}
    if cliente_id:
        q["cliente_id"] = cliente_id
    facturas = await db.facturas.find(q, {"_id": 0}).to_list(1000)
    clientes = {
        c["id"]: c
        for c in await db.clientes.find({}, {"_id": 0}).to_list(500)
    }
    result = []
    for f in facturas:
        c = clientes.get(f["cliente_id"], {})
        result.append({
            "id":              f["id"],
            "cliente_id":      f["cliente_id"],
            "cliente_nombre":  c.get("nombre", "—"),
            "documento":       f["numero_documento"],
            "fecha":           f["fecha_emision"],
            "valor_retenido":  f["retencion"],
        })
    return result
