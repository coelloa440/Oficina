"""Servicio del Reporte Ejecutivo Semanal: construcción HTML y envío."""
import logging
from datetime import date, timedelta

from database import get_db
from services.email import send_email

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _money(v: float) -> str:
    return f"${v:,.2f}"


# ──────────────────────────────────────────────
# Build HTML
# ──────────────────────────────────────────────

async def build_weekly_report_html() -> dict:
    """Construye el HTML del Reporte Ejecutivo Semanal y devuelve stats."""
    db = get_db()
    today = date.today()

    bancos   = await db.bancos.find({}, {"_id": 0}).to_list(200)
    cheques  = await db.cheques.find({}, {"_id": 0}).to_list(2000)
    facturas = await db.facturas.find({}, {"_id": 0}).to_list(2000)
    clientes = {
        c["id"]: c["nombre"]
        for c in await db.clientes.find({}, {"_id": 0}).to_list(500)
    }
    flujo = await db.flujo.find({}, {"_id": 0}).to_list(2000)

    # KPIs
    saldo_total    = sum(b["saldo_efectivo"] for b in bancos)
    sobregiro_disp = sum(b["sobregiro_asignado"] - b["sobregiro_utilizado"] for b in bancos)
    disponible     = saldo_total + sobregiro_disp
    cheques_pend   = [c for c in cheques if c["estado"] == "pendiente"]
    total_chq      = sum(c["valor"] for c in cheques_pend)
    cartera        = [f for f in facturas if f["estado"] == "pendiente"]
    total_cart     = sum(f["subtotal"] - f["anticipos"] - f["retencion"] for f in cartera)
    total_ret      = sum(f["retencion"] for f in facturas)

    # Cheques próximos 7 días
    proximos = []
    for c in cheques_pend:
        try:
            from datetime import datetime
            fc = datetime.fromisoformat(c["fecha_cobro"]).date()
            d  = (fc - today).days
            if 0 <= d <= 7:
                proximos.append((d, c))
        except Exception:
            pass
    proximos.sort(key=lambda x: x[0])

    # Top morosos (>30 días)
    morosos_map: dict = {}
    for f in cartera:
        try:
            from datetime import datetime
            fe   = datetime.fromisoformat(f["fecha_emision"]).date()
            dias = (today - fe).days
            if dias > 30:
                nm  = clientes.get(f["cliente_id"], "—")
                pen = f["subtotal"] - f["anticipos"] - f["retencion"]
                cur = morosos_map.get(nm, {"monto": 0.0, "dias_max": 0, "facturas": 0})
                cur["monto"]    += pen
                cur["dias_max"]  = max(cur["dias_max"], dias)
                cur["facturas"] += 1
                morosos_map[nm]  = cur
        except Exception:
            pass
    morosos = sorted(morosos_map.items(), key=lambda x: -x[1]["monto"])[:10]

    # Semanas críticas
    semanas = []
    start = today
    for w in range(4):
        ws_start = start + timedelta(days=w * 7)
        ws_end   = ws_start + timedelta(days=6)
        ws_in    = sum(x["monto"] for x in flujo if x["tipo"] == "ingreso" and ws_start.isoformat() <= x["fecha"] <= ws_end.isoformat())
        ws_out   = sum(x["monto"] for x in flujo if x["tipo"] == "egreso"  and ws_start.isoformat() <= x["fecha"] <= ws_end.isoformat())
        ws_chq   = sum(c["valor"] for c in cheques_pend if ws_start.isoformat() <= c.get("fecha_cobro", "") <= ws_end.isoformat())
        deficit  = ws_in - (ws_out + ws_chq)
        semanas.append({
            "rango": f"{ws_start.strftime('%d %b')} – {ws_end.strftime('%d %b')}",
            "ingresos": ws_in, "egresos": ws_out + ws_chq, "neto": deficit,
            "critica": deficit < 0,
        })

    # ── HTML ──
    def kpi_card(l, v, c="#0f172a"):
        return f"""<td style="padding:14px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;width:33%;">
  <div style="font-size:10px;letter-spacing:1.5px;color:#64748b;text-transform:uppercase;font-weight:700">{l}</div>
  <div style="font-size:22px;font-weight:700;color:{c};margin-top:6px;font-family:Georgia,serif;">{v}</div>
</td>"""

    proximos_html = "".join([
        f"""<tr>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;">{c['numero']}</td>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;">{c['beneficiario']}</td>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;text-align:center;color:{'#dc2626' if d<=2 else '#d97706'};font-weight:600">{d}d</td>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;text-align:right;font-weight:600">{_money(c['valor'])}</td>
        </tr>"""
        for d, c in proximos[:15]
    ]) or '<tr><td colspan="4" style="padding:14px;text-align:center;color:#94a3b8">Sin cheques en los próximos 7 días</td></tr>'

    morosos_html = "".join([
        f"""<tr>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;">{nm}</td>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;text-align:center">{m['facturas']}</td>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;text-align:center;color:#dc2626;font-weight:600">{m['dias_max']}d</td>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;text-align:right;font-weight:700">{_money(m['monto'])}</td>
        </tr>"""
        for nm, m in morosos
    ]) or '<tr><td colspan="4" style="padding:14px;text-align:center;color:#94a3b8">Sin clientes morosos</td></tr>'

    semanas_html = "".join([
        f"""<tr style="background:{'#fef2f2' if s['critica'] else '#f8fafc'}">
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;font-weight:600">{s['rango']} {'⚠️' if s['critica'] else ''}</td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:right;color:#15803d">{_money(s['ingresos'])}</td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:right;color:#b91c1c">{_money(s['egresos'])}</td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:right;font-weight:700;color:{'#dc2626' if s['critica'] else '#0f172a'}">{_money(s['neto'])}</td>
        </tr>"""
        for s in semanas
    ])

    html = f"""
<div style="max-width:720px;margin:0 auto;font-family:'Helvetica Neue',Arial,sans-serif;color:#0f172a;background:#f8fafc;padding:24px">
  <div style="background:#0f172a;color:white;padding:24px;border-radius:8px 8px 0 0">
    <div style="font-size:11px;letter-spacing:2px;color:#10b981;text-transform:uppercase;font-weight:700">Reporte Ejecutivo · Tesorería</div>
    <h1 style="margin:8px 0 0 0;font-family:Georgia,serif;font-size:28px">Cierre semanal</h1>
    <div style="margin-top:6px;color:#94a3b8;font-size:13px">{today.strftime('%A %d de %B, %Y').capitalize()}</div>
  </div>
  <div style="background:#fff;padding:20px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0">
    <h2 style="font-family:Georgia,serif;margin:0 0 12px 0;font-size:18px">Indicadores principales</h2>
    <table style="width:100%;border-collapse:separate;border-spacing:8px"><tr>
      {kpi_card("Saldo bancos", _money(saldo_total), "#0f766e")}
      {kpi_card("Disponible real", _money(disponible), "#0f766e")}
      {kpi_card("Cartera pendiente", _money(total_cart), "#1e40af")}
    </tr><tr>
      {kpi_card("Cheques pendientes", _money(total_chq), "#b45309")}
      {kpi_card("Retenciones", _money(total_ret), "#7c3aed")}
      {kpi_card("Bancos activos", str(len(bancos)))}
    </tr></table>
  </div>
  <div style="background:#fff;padding:20px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0">
    <h2 style="font-family:Georgia,serif;margin:0 0 12px 0;font-size:18px">Próximas 4 semanas · proyección</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead><tr style="background:#f1f5f9">
        <th style="padding:10px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#475569">Semana</th>
        <th style="padding:10px;text-align:right;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#475569">Ingresos</th>
        <th style="padding:10px;text-align:right;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#475569">Egresos</th>
        <th style="padding:10px;text-align:right;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#475569">Neto</th>
      </tr></thead>
      <tbody>{semanas_html}</tbody>
    </table>
  </div>
  <div style="background:#fff;padding:20px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0">
    <h2 style="font-family:Georgia,serif;margin:0 0 12px 0;font-size:18px">Cheques a cobrarse próxima semana</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead><tr style="background:#f1f5f9">
        <th style="padding:10px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#475569">N°</th>
        <th style="padding:10px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#475569">Beneficiario</th>
        <th style="padding:10px;text-align:center;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#475569">Días</th>
        <th style="padding:10px;text-align:right;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#475569">Valor</th>
      </tr></thead>
      <tbody>{proximos_html}</tbody>
    </table>
  </div>
  <div style="background:#fff;padding:20px;border:1px solid #e2e8f0;border-radius:0 0 8px 8px">
    <h2 style="font-family:Georgia,serif;margin:0 0 12px 0;font-size:18px">Top clientes morosos (&gt;30 días)</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead><tr style="background:#f1f5f9">
        <th style="padding:10px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#475569">Cliente</th>
        <th style="padding:10px;text-align:center;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#475569">Facturas</th>
        <th style="padding:10px;text-align:center;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#475569">Días máx</th>
        <th style="padding:10px;text-align:right;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#475569">Pendiente</th>
      </tr></thead>
      <tbody>{morosos_html}</tbody>
    </table>
  </div>
  <p style="margin-top:18px;font-size:11px;color:#94a3b8;text-align:center">
    Tesorería · Sistema Integral de Control Financiero · Reporte automático semanal
  </p>
</div>"""

    return {
        "html": html,
        "stats": {
            "saldo_total_bancos":       round(saldo_total, 2),
            "disponible_real":          round(disponible, 2),
            "total_cheques_pendientes": round(total_chq, 2),
            "cartera_pendiente":        round(total_cart, 2),
            "total_retenciones":        round(total_ret, 2),
            "cheques_proximos":         len(proximos),
            "morosos":                  len(morosos),
            "semanas_criticas":         sum(1 for s in semanas if s["critica"]),
        },
    }


# ──────────────────────────────────────────────
# Send
# ──────────────────────────────────────────────

async def send_weekly_report() -> dict:
    """Envía el reporte ejecutivo a admins y financieros."""
    db = get_db()
    report = await build_weekly_report_html()
    recipients = await db.users.find(
        {"role": {"$in": ["admin", "financiero"]}}, {"_id": 0, "email": 1}
    ).to_list(100)
    emails = [r["email"] for r in recipients if r.get("email")]
    if not emails:
        return {"sent": False, "reason": "Sin destinatarios", "stats": report["stats"]}

    from datetime import date
    subject     = f"Reporte Ejecutivo Semanal · {date.today().strftime('%d %b %Y')}"
    sent_count  = 0
    for em in emails:
        ok = await send_email(em, subject, report["html"])
        if ok:
            sent_count += 1

    logger.info(f"Reporte semanal: enviados {sent_count}/{len(emails)} · stats={report['stats']}")
    return {
        "sent":       sent_count > 0,
        "recipients": emails,
        "delivered":  sent_count,
        "stats":      report["stats"],
    }
