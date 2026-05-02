"""Router de alertas y envío de email de resumen."""
from datetime import date, datetime

from fastapi import APIRouter, Depends

from core import get_current_user, require_role
from database import get_db
from services.email import send_email

router = APIRouter(prefix="/alertas", tags=["alertas"])


@router.get("")
async def alertas(user: dict = Depends(get_current_user)):
    db     = get_db()
    alerts = []
    today  = date.today()

    # Cheques próximos (≤7 días, pendientes)
    cheques = await db.cheques.find({"estado": "pendiente"}, {"_id": 0}).to_list(2000)
    for c in cheques:
        try:
            fc   = datetime.fromisoformat(c["fecha_cobro"]).date()
            dias = (fc - today).days
            if dias <= 7:
                alerts.append({
                    "id":       f"ch-{c['id']}",
                    "tipo":     "cheque",
                    "priority": "high" if dias <= 2 else "warning",
                    "titulo":   f"Cheque #{c['numero']} vence en {dias} día(s)",
                    "detalle":  f"Beneficiario: {c['beneficiario']} · Valor: ${c['valor']:.2f}",
                    "fecha":    c["fecha_cobro"],
                })
        except Exception:
            pass

    # Sobregiro alto (>70 %)
    bancos = await db.bancos.find({}, {"_id": 0}).to_list(200)
    for b in bancos:
        if b["sobregiro_asignado"] > 0:
            uso = b["sobregiro_utilizado"] / b["sobregiro_asignado"]
            if uso > 0.7:
                alerts.append({
                    "id":       f"sg-{b['id']}",
                    "tipo":     "sobregiro",
                    "priority": "high" if uso > 0.9 else "warning",
                    "titulo":   f"Sobregiro alto en {b['nombre']}",
                    "detalle":  f"Uso: {uso*100:.1f}% · Disponible: ${b['saldo_efectivo']+b['sobregiro_asignado']-b['sobregiro_utilizado']:.2f}",
                    "fecha":    today.isoformat(),
                })
        if b["saldo_efectivo"] < 1000:
            alerts.append({
                "id":       f"sb-{b['id']}",
                "tipo":     "saldo_bajo",
                "priority": "warning",
                "titulo":   f"Saldo bajo en {b['nombre']}",
                "detalle":  f"Saldo efectivo: ${b['saldo_efectivo']:.2f}",
                "fecha":    today.isoformat(),
            })

    # Facturas vencidas (>30 días)
    facturas = await db.facturas.find({"estado": "pendiente"}, {"_id": 0}).to_list(2000)
    clientes = {c["id"]: c["nombre"] for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}
    for f in facturas:
        try:
            fe   = datetime.fromisoformat(f["fecha_emision"]).date()
            dias = (today - fe).days
            if dias > 30:
                alerts.append({
                    "id":       f"fc-{f['id']}",
                    "tipo":     "cliente_pendiente",
                    "priority": "high" if dias > 60 else "info",
                    "titulo":   f"Factura vencida {dias} días",
                    "detalle":  f"Cliente: {clientes.get(f['cliente_id'],'—')} · Doc: {f['numero_documento']}",
                    "fecha":    f["fecha_emision"],
                })
        except Exception:
            pass

    priority_order = {"high": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: priority_order.get(a["priority"], 3))
    return alerts


@router.post("/enviar-email")
async def enviar_alertas_email(user: dict = Depends(require_role("admin", "financiero"))):
    als = await alertas(user)
    if not als:
        return {"sent": False, "reason": "Sin alertas"}
    rows = "".join([
        f"<tr><td style='padding:8px;border-bottom:1px solid #eee;'><b>{a['titulo']}</b><br/><span style='color:#666'>{a['detalle']}</span></td></tr>"
        for a in als[:20]
    ])
    html = f"<h2>Resumen de Alertas Financieras</h2><table style='width:100%;border-collapse:collapse;font-family:sans-serif'>{rows}</table>"
    ok   = await send_email(user["email"], "Alertas Financieras · Resumen", html)
    return {"sent": ok, "count": len(als)}
