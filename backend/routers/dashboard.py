"""Router del dashboard gerencial."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends

from core import get_current_user
from database import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard(user: dict = Depends(get_current_user)):
    db       = get_db()
    bancos   = await db.bancos.find({}, {"_id": 0}).to_list(200)
    cheques  = await db.cheques.find({}, {"_id": 0}).to_list(2000)
    facturas = await db.facturas.find({}, {"_id": 0}).to_list(2000)
    clientes = await db.clientes.find({}, {"_id": 0}).to_list(500)
    flujo    = await db.flujo.find({}, {"_id": 0}).to_list(2000)

    saldo_total     = sum(b["saldo_efectivo"] for b in bancos)
    sobregiro_disp  = sum(b["sobregiro_asignado"] - b["sobregiro_utilizado"] for b in bancos)
    disponible_real = round(saldo_total + sobregiro_disp, 2)

    cheques_pend            = [c for c in cheques if c["estado"] == "pendiente"]
    total_cheques_pendientes = round(sum(c["valor"] for c in cheques_pend), 2)

    cartera_pend    = [f for f in facturas if f["estado"] == "pendiente"]
    cartera_total   = round(sum(f["subtotal"] - f["anticipos"] - f["retencion"] for f in cartera_pend), 2)
    total_retenciones = round(sum(f["retencion"] for f in facturas), 2)

    # Cheques por estado
    por_estado = {"cobrado": 0, "pendiente": 0, "anulado": 0}
    for c in cheques:
        por_estado[c["estado"]] = por_estado.get(c["estado"], 0) + 1

    # Cartera por cliente
    cliente_map = {c["id"]: c["nombre"] for c in clientes}
    por_cliente: dict = {}
    for f in cartera_pend:
        nm = cliente_map.get(f["cliente_id"], "—")
        por_cliente[nm] = por_cliente.get(nm, 0) + (f["subtotal"] - f["anticipos"] - f["retencion"])
    cartera_cliente_data = [
        {"cliente": k, "monto": round(v, 2)}
        for k, v in sorted(por_cliente.items(), key=lambda x: -x[1])[:8]
    ]

    # Flujo próximos 7 días
    today = date.today()
    dias  = []
    for i in range(7):
        d  = today + timedelta(days=i)
        ds = d.isoformat()
        ingresos = sum(x["monto"] for x in flujo if x["fecha"] == ds and x["tipo"] == "ingreso")
        egresos  = sum(x["monto"] for x in flujo if x["fecha"] == ds and x["tipo"] == "egreso")
        dias.append({"fecha": ds, "dia": d.strftime("%a"), "ingresos": round(ingresos, 2), "egresos": round(egresos, 2)})

    return {
        "kpis": {
            "saldo_total_bancos":        round(saldo_total, 2),
            "total_cheques_pendientes":  total_cheques_pendientes,
            "cartera_pendiente":         cartera_total,
            "total_retenciones":         total_retenciones,
            "disponible_real":           disponible_real,
        },
        "cheques_por_estado":  [{"estado": k, "cantidad": v} for k, v in por_estado.items()],
        "cartera_por_cliente": cartera_cliente_data,
        "flujo_7dias":         dias,
        "bancos": [
            {**b, "disponible": round(b["saldo_efectivo"] + b["sobregiro_asignado"] - b["sobregiro_utilizado"], 2)}
            for b in bancos
        ],
    }
