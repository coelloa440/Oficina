"""Router de exportación: Excel (openpyxl) y PDF (ReportLab)."""
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from core import get_current_user
from database import get_db

router = APIRouter(prefix="/export", tags=["exports"])
TZ_EC  = ZoneInfo("America/Guayaquil")

# ──────────────────────────────────────────────
# Color palette (PDF)
# ──────────────────────────────────────────────
NAVY      = colors.HexColor("#0f172a")
TEAL      = colors.HexColor("#0f766e")
SLATE_50  = colors.HexColor("#f8fafc")
SLATE_200 = colors.HexColor("#e2e8f0")
SLATE_500 = colors.HexColor("#64748b")
BLUE      = colors.HexColor("#1e40af")


# ──────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────

def _excel_response(wb: Workbook, filename: str) -> StreamingResponse:
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _pdf_response(elements: list, filename: str, landscape_mode: bool = False) -> StreamingResponse:
    buf  = BytesIO()
    page = landscape(A4) if landscape_mode else A4
    doc  = SimpleDocTemplate(
        buf, pagesize=page,
        leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm,
        title=filename,
    )
    doc.build(elements)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _fmt_money(v) -> str:
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return str(v)


def _pdf_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title":    ParagraphStyle("title",    parent=base["Title"],    fontSize=20, leading=24, textColor=NAVY, spaceAfter=4),
        "subtitle": ParagraphStyle("sub",      parent=base["Normal"],   fontSize=9,  textColor=SLATE_500, spaceAfter=16),
        "h2":       ParagraphStyle("h2",       parent=base["Heading2"], fontSize=13, textColor=NAVY, spaceBefore=14, spaceAfter=8),
        "small":    ParagraphStyle("sm",       parent=base["Normal"],   fontSize=8,  textColor=SLATE_500),
        "overline": ParagraphStyle("ov",       parent=base["Normal"],   fontSize=7,  textColor=SLATE_500, spaceAfter=2),
    }


def _header(title: str, subtitle: str = "") -> list:
    st  = _pdf_styles()
    sub = subtitle or f"Generado: {datetime.now(TZ_EC).strftime('%d %b %Y · %H:%M')} (Ecuador)"
    return [
        Paragraph("TESORERÍA · CONTROL FINANCIERO", st["overline"]),
        Paragraph(title, st["title"]),
        Paragraph(sub, st["subtitle"]),
    ]


def _table_style(header_bg=NAVY, header_color=colors.white) -> TableStyle:
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  header_bg),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  header_color),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  8),
        ("FONTSIZE",      (0, 1), (-1, -1), 8.5),
        ("ALIGN",         (0, 0), (-1, 0),  "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",          (0, 0), (-1, -1), 0.25, SLATE_200),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, SLATE_50]),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ])


# ──────────────────────────────────────────────
# Excel
# ──────────────────────────────────────────────

@router.get("/{modulo}")
async def export_excel(modulo: str, user: dict = Depends(get_current_user)):
    db = get_db()
    wb = Workbook()
    ws = wb.active

    if modulo == "cheques":
        ws.title = "Cheques"
        bancos   = {b["id"]: b["nombre"] for b in await db.bancos.find({}, {"_id": 0}).to_list(200)}
        ws.append(["Banco", "Número", "Valor", "Beneficiario", "Fecha Emisión", "Fecha Cobro", "Estado", "Motivo"])
        for c in await db.cheques.find({}, {"_id": 0}).sort([("banco_id", 1), ("fecha_cobro", 1)]).to_list(2000):
            ws.append([bancos.get(c.get("banco_id"), "—"), c["numero"], c["valor"], c["beneficiario"],
                       c["fecha_emision"], c["fecha_cobro"], c["estado"], c.get("motivo", "")])

    elif modulo == "cartera":
        ws.title  = "Cartera"
        clientes  = {c["id"]: c["nombre"] for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}
        ws.append(["Cliente", "Documento", "Fecha", "Estado", "Subtotal", "Anticipos", "Retención", "Total"])
        for f in await db.facturas.find({}, {"_id": 0}).to_list(2000):
            t = f["subtotal"] - f["anticipos"] - f["retencion"]
            ws.append([clientes.get(f["cliente_id"], "—"), f["numero_documento"], f["fecha_emision"],
                       f["estado"], f["subtotal"], f["anticipos"], f["retencion"], round(t, 2)])

    elif modulo == "retenciones":
        ws.title = "Retenciones"
        clientes = {c["id"]: c["nombre"] for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}
        ws.append(["Cliente", "Documento", "Fecha", "Valor Retenido"])
        for f in await db.facturas.find({"retencion": {"$gt": 0}}, {"_id": 0}).to_list(2000):
            ws.append([clientes.get(f["cliente_id"], "—"), f["numero_documento"], f["fecha_emision"], f["retencion"]])

    elif modulo == "bancos":
        ws.title = "Bancos"
        ws.append(["Banco", "Saldo", "Sobregiro Asignado", "Sobregiro Utilizado", "Disponible"])
        for b in await db.bancos.find({}, {"_id": 0}).to_list(200):
            disp = b["saldo_efectivo"] + b["sobregiro_asignado"] - b["sobregiro_utilizado"]
            ws.append([b["nombre"], b["saldo_efectivo"], b["sobregiro_asignado"], b["sobregiro_utilizado"], round(disp, 2)])

    elif modulo == "flujo":
        ws.title = "Flujo"
        ws.append(["Fecha", "Tipo", "Descripción", "Monto"])
        for x in await db.flujo.find({}, {"_id": 0}).to_list(2000):
            ws.append([x["fecha"], x["tipo"], x["descripcion"], x["monto"]])

    else:
        raise HTTPException(400, "Módulo inválido")

    return _excel_response(wb, f"{modulo}.xlsx")


# ──────────────────────────────────────────────
# PDF
# ──────────────────────────────────────────────

@router.get("/pdf/{modulo}")
async def export_pdf(modulo: str, user: dict = Depends(get_current_user)):
    db       = get_db()
    st       = _pdf_styles()
    elements = []

    if modulo == "cheques":
        elements += _header("Estado de Cheques Emitidos")
        bancos = {b["id"]: b["nombre"] for b in await db.bancos.find({}, {"_id": 0}).to_list(200)}
        rows   = [["Banco", "N°", "Beneficiario", "Emisión", "Cobro", "Valor", "Estado"]]
        items  = await db.cheques.find({}, {"_id": 0}).sort([("banco_id", 1), ("fecha_cobro", 1)]).to_list(2000)
        total  = 0.0
        for c in items:
            rows.append([bancos.get(c.get("banco_id"), "—"), c["numero"], c["beneficiario"][:28],
                         c["fecha_emision"], c["fecha_cobro"], _fmt_money(c["valor"]), c["estado"].capitalize()])
            if c["estado"] == "pendiente":
                total += c["valor"]
        t = Table(rows, repeatRows=1, colWidths=[32*mm, 22*mm, 55*mm, 22*mm, 22*mm, 24*mm, 22*mm])
        t.setStyle(_table_style())
        elements += [t, Spacer(1, 10), Paragraph(f"<b>Total pendiente:</b> {_fmt_money(total)} · {len(items)} cheques", st["small"])]
        return _pdf_response(elements, "cheques.pdf", landscape_mode=True)

    if modulo == "cartera":
        elements += _header("Cartera de Clientes")
        clientes = {c["id"]: c["nombre"] for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}
        rows     = [["Cliente", "Documento", "Fecha", "Subtotal", "Anticipos", "Retención", "Total", "Estado"]]
        items    = await db.facturas.find({}, {"_id": 0}).sort("fecha_emision", -1).to_list(2000)
        total_p  = 0.0
        for f in items:
            tot = f["subtotal"] - f["anticipos"] - f["retencion"]
            rows.append([clientes.get(f["cliente_id"], "—")[:28], f["numero_documento"], f["fecha_emision"],
                         _fmt_money(f["subtotal"]), _fmt_money(f["anticipos"]), _fmt_money(f["retencion"]),
                         _fmt_money(tot), f["estado"].capitalize()])
            if f["estado"] == "pendiente":
                total_p += tot
        t = Table(rows, repeatRows=1, colWidths=[50*mm, 22*mm, 22*mm, 22*mm, 22*mm, 22*mm, 24*mm, 22*mm])
        t.setStyle(_table_style())
        elements += [t, Spacer(1, 10), Paragraph(f"<b>Total cartera pendiente:</b> {_fmt_money(total_p)}", st["small"])]
        return _pdf_response(elements, "cartera.pdf", landscape_mode=True)

    if modulo == "retenciones":
        elements += _header("Consolidado de Retenciones")
        clientes = {c["id"]: c["nombre"] for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}
        items    = await db.facturas.find({"retencion": {"$gt": 0}}, {"_id": 0}).to_list(2000)
        rows     = [["Cliente", "Documento", "Fecha", "Valor Retenido"]]
        total    = 0.0
        for f in items:
            rows.append([clientes.get(f["cliente_id"], "—"), f["numero_documento"], f["fecha_emision"], _fmt_money(f["retencion"])])
            total += f["retencion"]
        t = Table(rows, repeatRows=1, colWidths=[75*mm, 35*mm, 30*mm, 34*mm])
        t.setStyle(_table_style())
        elements += [t, Spacer(1, 10), Paragraph(f"<b>Total retenciones:</b> {_fmt_money(total)}", st["small"])]
        return _pdf_response(elements, "retenciones.pdf")

    if modulo == "bancos":
        elements += _header("Movimientos y Posición Bancaria")
        bancos = await db.bancos.find({}, {"_id": 0}).to_list(200)
        rows   = [["Banco", "Saldo", "Sobregiro Asig.", "Sobregiro Usado", "Disponible"]]
        tot_s  = tot_d = 0.0
        for b in bancos:
            disp = b["saldo_efectivo"] + b["sobregiro_asignado"] - b["sobregiro_utilizado"]
            rows.append([b["nombre"], _fmt_money(b["saldo_efectivo"]), _fmt_money(b["sobregiro_asignado"]),
                         _fmt_money(b["sobregiro_utilizado"]), _fmt_money(disp)])
            tot_s += b["saldo_efectivo"]
            tot_d += disp
        t = Table(rows, repeatRows=1, colWidths=[50*mm, 30*mm, 32*mm, 32*mm, 30*mm])
        t.setStyle(_table_style())
        elements += [t, Spacer(1, 10),
                     Paragraph(f"<b>Saldo consolidado:</b> {_fmt_money(tot_s)} · <b>Disponible real:</b> {_fmt_money(tot_d)}", st["small"])]
        return _pdf_response(elements, "bancos.pdf")

    if modulo == "flujo":
        elements += _header("Flujo Financiero")
        bancos = {b["id"]: b["nombre"] for b in await db.bancos.find({}, {"_id": 0}).to_list(200)}
        items  = await db.flujo.find({}, {"_id": 0}).sort("fecha", 1).to_list(2000)
        rows   = [["Fecha", "Tipo", "Descripción", "Banco", "Monto"]]
        tot_i  = tot_o = 0.0
        for x in items:
            rows.append([x["fecha"], x["tipo"].capitalize(), x["descripcion"][:38],
                         bancos.get(x.get("banco_id"), "—"), _fmt_money(x["monto"])])
            if x["tipo"] == "ingreso": tot_i += x["monto"]
            else:                      tot_o += x["monto"]
        t = Table(rows, repeatRows=1, colWidths=[28*mm, 22*mm, 70*mm, 40*mm, 24*mm])
        t.setStyle(_table_style())
        elements += [t, Spacer(1, 10),
                     Paragraph(f"<b>Ingresos:</b> {_fmt_money(tot_i)} · <b>Egresos:</b> {_fmt_money(tot_o)} · <b>Neto:</b> {_fmt_money(tot_i-tot_o)}", st["small"])]
        return _pdf_response(elements, "flujo.pdf", landscape_mode=True)

    if modulo == "gerencial":
        elements += _header("Reporte Gerencial Consolidado")
        bancos   = await db.bancos.find({}, {"_id": 0}).to_list(200)
        cheques  = await db.cheques.find({}, {"_id": 0}).to_list(2000)
        facturas = await db.facturas.find({}, {"_id": 0}).to_list(2000)
        clientes = {c["id"]: c["nombre"] for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}

        saldo    = sum(b["saldo_efectivo"] for b in bancos)
        disp     = saldo + sum(b["sobregiro_asignado"] - b["sobregiro_utilizado"] for b in bancos)
        chq_pend = sum(c["valor"] for c in cheques if c["estado"] == "pendiente")
        cart     = sum(f["subtotal"] - f["anticipos"] - f["retencion"] for f in facturas if f["estado"] == "pendiente")
        ret      = sum(f["retencion"] for f in facturas)

        kpi_rows = [
            ["INDICADOR", "VALOR"],
            ["Saldo consolidado bancos",         _fmt_money(saldo)],
            ["Disponible real (con sobregiro)",  _fmt_money(disp)],
            ["Cheques pendientes de cobro",      _fmt_money(chq_pend)],
            ["Cartera pendiente por cobrar",     _fmt_money(cart)],
            ["Total retenciones aplicadas",      _fmt_money(ret)],
        ]
        t = Table(kpi_rows, colWidths=[110*mm, 60*mm])
        t.setStyle(_table_style())
        elements.append(t)

        elements.append(Paragraph("Posición bancaria", st["h2"]))
        b_rows = [["Banco", "Saldo", "Sobregiro Usado", "Disponible"]]
        for b in bancos:
            d = b["saldo_efectivo"] + b["sobregiro_asignado"] - b["sobregiro_utilizado"]
            b_rows.append([b["nombre"], _fmt_money(b["saldo_efectivo"]), _fmt_money(b["sobregiro_utilizado"]), _fmt_money(d)])
        tb = Table(b_rows, repeatRows=1, colWidths=[60*mm, 36*mm, 40*mm, 34*mm])
        tb.setStyle(_table_style(header_bg=TEAL))
        elements.append(tb)

        elements.append(Paragraph("Top 5 clientes con mayor cartera pendiente", st["h2"]))
        bucket: dict = {}
        for f in facturas:
            if f["estado"] != "pendiente":
                continue
            nm = clientes.get(f["cliente_id"], "—")
            bucket[nm] = bucket.get(nm, 0) + (f["subtotal"] - f["anticipos"] - f["retencion"])
        top    = sorted(bucket.items(), key=lambda x: -x[1])[:5]
        c_rows = [["Cliente", "Pendiente"]] + [[nm, _fmt_money(v)] for nm, v in top]
        if len(c_rows) == 1:
            c_rows.append(["Sin cartera pendiente", "—"])
        tc = Table(c_rows, repeatRows=1, colWidths=[120*mm, 50*mm])
        tc.setStyle(_table_style(header_bg=BLUE))
        elements.append(tc)

        elements += [Spacer(1, 14),
                     Paragraph("Documento generado automáticamente por el Sistema Integral de Control Financiero.", st["small"])]
        return _pdf_response(elements, "reporte_gerencial.pdf")

    raise HTTPException(400, "Módulo inválido")
