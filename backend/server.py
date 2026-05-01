from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta, date
from typing import List, Optional, Literal
from io import BytesIO

import bcrypt
import jwt
import resend
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, Query
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from openpyxl import Workbook
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak

# -----------------------------
# Setup
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_ALGORITHM = "HS256"
JWT_SECRET = os.environ["JWT_SECRET"]
resend.api_key = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")

app = FastAPI(title="Sistema Integral de Control Financiero y Cartera")
api = APIRouter(prefix="/api")
scheduler = None  # set on startup

# -----------------------------
# Helpers
# -----------------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

def new_id() -> str:
    return str(uuid.uuid4())

def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id, "email": email, "role": role,
        "exp": now_utc() + timedelta(hours=12), "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesión expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

def require_role(*roles: str):
    async def checker(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Permiso insuficiente")
        return user
    return checker

async def send_alert_email(to: str, subject: str, body_html: str) -> bool:
    if not resend.api_key:
        logger.info(f"[EMAIL STUB] To:{to} Subject:{subject}")
        return False
    try:
        params = {"from": SENDER_EMAIL, "to": [to], "subject": subject, "html": body_html}
        await asyncio.to_thread(resend.Emails.send, params)
        return True
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False

# -----------------------------
# Models
# -----------------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["admin", "financiero", "consulta"] = "consulta"

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class BankIn(BaseModel):
    nombre: str
    saldo_efectivo: float = 0.0
    sobregiro_asignado: float = 0.0
    sobregiro_utilizado: float = 0.0
    color: Optional[str] = "#1e40af"

class ClienteIn(BaseModel):
    nombre: str
    ruc: Optional[str] = ""
    contacto: Optional[str] = ""
    email: Optional[str] = ""

class ChequeIn(BaseModel):
    numero: str
    valor: float
    beneficiario: str
    fecha_emision: str  # ISO date
    fecha_cobro: str    # ISO date
    motivo: str = ""
    estado: Literal["cobrado", "pendiente", "anulado"] = "pendiente"
    banco_id: str

class FacturaIn(BaseModel):
    cliente_id: str
    numero_documento: str
    fecha_emision: str
    estado: Literal["pendiente", "recibida"] = "pendiente"
    subtotal: float
    anticipos: float = 0.0
    retencion: float = 0.0

class FlujoIn(BaseModel):
    fecha: str  # ISO date
    tipo: Literal["ingreso", "egreso"]
    descripcion: str
    monto: float
    banco_id: Optional[str] = None

# -----------------------------
# AUTH
# -----------------------------
@api.post("/auth/register")
async def register(body: UserCreate, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email ya registrado")
    user = {
        "id": new_id(), "email": email, "password_hash": hash_password(body.password),
        "name": body.name, "role": body.role, "created_at": iso(now_utc())
    }
    await db.users.insert_one(user)
    token = create_access_token(user["id"], email, body.role)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=43200, path="/")
    return {"id": user["id"], "email": email, "name": body.name, "role": body.role}

@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_access_token(user["id"], email, user["role"])
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=43200, path="/")
    return {"id": user["id"], "email": email, "name": user["name"], "role": user["role"]}

@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}

@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user

# -----------------------------
# BANCOS
# -----------------------------
@api.get("/bancos")
async def list_bancos(user: dict = Depends(get_current_user)):
    items = await db.bancos.find({}, {"_id": 0}).to_list(200)
    for b in items:
        b["disponible"] = round(b["saldo_efectivo"] + b["sobregiro_asignado"] - b["sobregiro_utilizado"], 2)
    return items

@api.post("/bancos")
async def create_banco(body: BankIn, user: dict = Depends(require_role("admin", "financiero"))):
    doc = {"id": new_id(), **body.model_dump(), "created_at": iso(now_utc())}
    await db.bancos.insert_one(doc.copy())
    doc["disponible"] = round(doc["saldo_efectivo"] + doc["sobregiro_asignado"] - doc["sobregiro_utilizado"], 2)
    return doc

@api.put("/bancos/{banco_id}")
async def update_banco(banco_id: str, body: BankIn, user: dict = Depends(require_role("admin", "financiero"))):
    res = await db.bancos.update_one({"id": banco_id}, {"$set": body.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Banco no encontrado")
    doc = await db.bancos.find_one({"id": banco_id}, {"_id": 0})
    doc["disponible"] = round(doc["saldo_efectivo"] + doc["sobregiro_asignado"] - doc["sobregiro_utilizado"], 2)
    return doc

@api.delete("/bancos/{banco_id}")
async def delete_banco(banco_id: str, force: bool = False, user: dict = Depends(require_role("admin"))):
    cheques_count = await db.cheques.count_documents({"banco_id": banco_id})
    flujo_count = await db.flujo.count_documents({"banco_id": banco_id})
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
    return {"ok": True, "cheques_eliminados": cheques_count if force else 0, "flujo_eliminados": flujo_count if force else 0}

# -----------------------------
# CLIENTES
# -----------------------------
@api.get("/clientes")
async def list_clientes(user: dict = Depends(get_current_user)):
    return await db.clientes.find({}, {"_id": 0}).to_list(500)

@api.post("/clientes")
async def create_cliente(body: ClienteIn, user: dict = Depends(require_role("admin", "financiero"))):
    doc = {"id": new_id(), **body.model_dump(), "created_at": iso(now_utc())}
    await db.clientes.insert_one(doc.copy())
    return doc

@api.put("/clientes/{cid}")
async def update_cliente(cid: str, body: ClienteIn, user: dict = Depends(require_role("admin", "financiero"))):
    res = await db.clientes.update_one({"id": cid}, {"$set": body.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Cliente no encontrado")
    return await db.clientes.find_one({"id": cid}, {"_id": 0})

@api.delete("/clientes/{cid}")
async def delete_cliente(cid: str, user: dict = Depends(require_role("admin"))):
    await db.clientes.delete_one({"id": cid})
    await db.facturas.delete_many({"cliente_id": cid})
    return {"ok": True}

# -----------------------------
# CHEQUES
# -----------------------------
def _cheque_enrich(ch: dict) -> dict:
    try:
        d = datetime.fromisoformat(ch["fecha_cobro"]).date()
        today = date.today()
        ch["dias_restantes"] = (d - today).days
    except Exception:
        ch["dias_restantes"] = None
    return ch

@api.get("/cheques")
async def list_cheques(estado: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {}
    if estado:
        q["estado"] = estado
    items = await db.cheques.find(q, {"_id": 0}).sort("fecha_cobro", 1).to_list(1000)
    bancos = {b["id"]: b["nombre"] for b in await db.bancos.find({}, {"_id": 0}).to_list(200)}
    enriched = []
    for c in items:
        c = _cheque_enrich(c)
        c["banco_nombre"] = bancos.get(c.get("banco_id"), "—")
        enriched.append(c)
    return enriched

@api.post("/cheques")
async def create_cheque(body: ChequeIn, user: dict = Depends(require_role("admin", "financiero"))):
    doc = {"id": new_id(), **body.model_dump(), "created_at": iso(now_utc())}
    await db.cheques.insert_one(doc.copy())
    # si ya está cobrado, descontar del banco
    if doc["estado"] == "cobrado":
        await db.bancos.update_one({"id": doc["banco_id"]}, {"$inc": {"saldo_efectivo": -doc["valor"]}})
    return _cheque_enrich(doc)

@api.put("/cheques/{cid}")
async def update_cheque(cid: str, body: ChequeIn, user: dict = Depends(require_role("admin", "financiero"))):
    prev = await db.cheques.find_one({"id": cid}, {"_id": 0})
    if not prev:
        raise HTTPException(404, "Cheque no encontrado")
    await db.cheques.update_one({"id": cid}, {"$set": body.model_dump()})
    new = await db.cheques.find_one({"id": cid}, {"_id": 0})
    # Transición a cobrado => descontar saldo
    if prev["estado"] != "cobrado" and new["estado"] == "cobrado":
        await db.bancos.update_one({"id": new["banco_id"]}, {"$inc": {"saldo_efectivo": -new["valor"]}})
    # Si se revierte de cobrado a otro estado, reponer
    if prev["estado"] == "cobrado" and new["estado"] != "cobrado":
        await db.bancos.update_one({"id": prev["banco_id"]}, {"$inc": {"saldo_efectivo": prev["valor"]}})
    return _cheque_enrich(new)

@api.delete("/cheques/{cid}")
async def delete_cheque(cid: str, user: dict = Depends(require_role("admin"))):
    await db.cheques.delete_one({"id": cid})
    return {"ok": True}

# -----------------------------
# CARTERA (Facturas)
# -----------------------------
def _factura_total(f: dict) -> dict:
    f["total"] = round(f["subtotal"] - f["anticipos"] - f["retencion"], 2)
    return f

@api.get("/facturas")
async def list_facturas(cliente_id: Optional[str] = None, desde: Optional[str] = None, hasta: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {}
    if cliente_id:
        q["cliente_id"] = cliente_id
    if desde or hasta:
        q["fecha_emision"] = {}
        if desde:
            q["fecha_emision"]["$gte"] = desde
        if hasta:
            q["fecha_emision"]["$lte"] = hasta
    items = await db.facturas.find(q, {"_id": 0}).sort("fecha_emision", -1).to_list(1000)
    return [_factura_total(f) for f in items]

@api.post("/facturas")
async def create_factura(body: FacturaIn, user: dict = Depends(require_role("admin", "financiero"))):
    doc = {"id": new_id(), **body.model_dump(), "created_at": iso(now_utc())}
    await db.facturas.insert_one(doc.copy())
    return _factura_total(doc)

@api.put("/facturas/{fid}")
async def update_factura(fid: str, body: FacturaIn, user: dict = Depends(require_role("admin", "financiero"))):
    res = await db.facturas.update_one({"id": fid}, {"$set": body.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Factura no encontrada")
    doc = await db.facturas.find_one({"id": fid}, {"_id": 0})
    return _factura_total(doc)

@api.delete("/facturas/{fid}")
async def delete_factura(fid: str, user: dict = Depends(require_role("admin"))):
    await db.facturas.delete_one({"id": fid})
    return {"ok": True}

# -----------------------------
# RETENCIONES
# -----------------------------
@api.get("/retenciones")
async def list_retenciones(cliente_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"retencion": {"$gt": 0}}
    if cliente_id:
        q["cliente_id"] = cliente_id
    facturas = await db.facturas.find(q, {"_id": 0}).to_list(1000)
    clientes = {c["id"]: c for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}
    result = []
    for f in facturas:
        c = clientes.get(f["cliente_id"], {})
        result.append({
            "id": f["id"],
            "cliente_id": f["cliente_id"],
            "cliente_nombre": c.get("nombre", "—"),
            "documento": f["numero_documento"],
            "fecha": f["fecha_emision"],
            "valor_retenido": f["retencion"],
        })
    return result

# -----------------------------
# FLUJO SEMANAL
# -----------------------------
@api.get("/flujo")
async def list_flujo(desde: Optional[str] = None, hasta: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {}
    if desde or hasta:
        q["fecha"] = {}
        if desde:
            q["fecha"]["$gte"] = desde
        if hasta:
            q["fecha"]["$lte"] = hasta
    return await db.flujo.find(q, {"_id": 0}).sort("fecha", 1).to_list(1000)

@api.post("/flujo")
async def create_flujo(body: FlujoIn, user: dict = Depends(require_role("admin", "financiero"))):
    doc = {"id": new_id(), **body.model_dump(), "created_at": iso(now_utc())}
    await db.flujo.insert_one(doc.copy())
    return doc

@api.delete("/flujo/{fid}")
async def delete_flujo(fid: str, user: dict = Depends(require_role("admin", "financiero"))):
    await db.flujo.delete_one({"id": fid})
    return {"ok": True}

# -----------------------------
# DASHBOARD
# -----------------------------
@api.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    bancos = await db.bancos.find({}, {"_id": 0}).to_list(200)
    cheques = await db.cheques.find({}, {"_id": 0}).to_list(2000)
    facturas = await db.facturas.find({}, {"_id": 0}).to_list(2000)
    clientes = await db.clientes.find({}, {"_id": 0}).to_list(500)
    flujo = await db.flujo.find({}, {"_id": 0}).to_list(2000)

    saldo_total = sum(b["saldo_efectivo"] for b in bancos)
    sobregiro_disp = sum(b["sobregiro_asignado"] - b["sobregiro_utilizado"] for b in bancos)
    disponible_real = round(saldo_total + sobregiro_disp, 2)

    cheques_pendientes = [c for c in cheques if c["estado"] == "pendiente"]
    total_cheques_pendientes = round(sum(c["valor"] for c in cheques_pendientes), 2)

    cartera_pendiente_items = [f for f in facturas if f["estado"] == "pendiente"]
    cartera_pendiente_total = round(sum(f["subtotal"] - f["anticipos"] - f["retencion"] for f in cartera_pendiente_items), 2)

    total_retenciones = round(sum(f["retencion"] for f in facturas), 2)

    # Cheques por estado
    por_estado = {"cobrado": 0, "pendiente": 0, "anulado": 0}
    for c in cheques:
        por_estado[c["estado"]] = por_estado.get(c["estado"], 0) + 1

    # Cartera por cliente
    cliente_map = {c["id"]: c["nombre"] for c in clientes}
    por_cliente = {}
    for f in cartera_pendiente_items:
        nm = cliente_map.get(f["cliente_id"], "—")
        por_cliente[nm] = por_cliente.get(nm, 0) + (f["subtotal"] - f["anticipos"] - f["retencion"])
    cartera_cliente_data = [{"cliente": k, "monto": round(v, 2)} for k, v in sorted(por_cliente.items(), key=lambda x: -x[1])[:8]]

    # Flujo próximos 7 días
    today = date.today()
    dias = []
    for i in range(7):
        d = today + timedelta(days=i)
        ds = d.isoformat()
        ingresos = sum(x["monto"] for x in flujo if x["fecha"] == ds and x["tipo"] == "ingreso")
        egresos = sum(x["monto"] for x in flujo if x["fecha"] == ds and x["tipo"] == "egreso")
        dias.append({"fecha": ds, "dia": d.strftime("%a"), "ingresos": round(ingresos, 2), "egresos": round(egresos, 2)})

    return {
        "kpis": {
            "saldo_total_bancos": round(saldo_total, 2),
            "total_cheques_pendientes": total_cheques_pendientes,
            "cartera_pendiente": cartera_pendiente_total,
            "total_retenciones": total_retenciones,
            "disponible_real": disponible_real,
        },
        "cheques_por_estado": [{"estado": k, "cantidad": v} for k, v in por_estado.items()],
        "cartera_por_cliente": cartera_cliente_data,
        "flujo_7dias": dias,
        "bancos": [{**b, "disponible": round(b["saldo_efectivo"] + b["sobregiro_asignado"] - b["sobregiro_utilizado"], 2)} for b in bancos],
    }

# -----------------------------
# ALERTAS
# -----------------------------
@api.get("/alertas")
async def alertas(user: dict = Depends(get_current_user)):
    alerts = []
    today = date.today()

    # Cheques próximos (<=7 días, pendientes)
    cheques = await db.cheques.find({"estado": "pendiente"}, {"_id": 0}).to_list(2000)
    for c in cheques:
        try:
            fc = datetime.fromisoformat(c["fecha_cobro"]).date()
            dias = (fc - today).days
            if dias <= 7:
                priority = "high" if dias <= 2 else "warning"
                alerts.append({
                    "id": f"ch-{c['id']}", "tipo": "cheque",
                    "priority": priority,
                    "titulo": f"Cheque #{c['numero']} vence en {dias} día(s)",
                    "detalle": f"Beneficiario: {c['beneficiario']} · Valor: ${c['valor']:.2f}",
                    "fecha": c["fecha_cobro"],
                })
        except Exception:
            pass

    # Sobregiro alto (>70%)
    bancos = await db.bancos.find({}, {"_id": 0}).to_list(200)
    for b in bancos:
        if b["sobregiro_asignado"] > 0:
            uso = b["sobregiro_utilizado"] / b["sobregiro_asignado"]
            if uso > 0.7:
                alerts.append({
                    "id": f"sg-{b['id']}", "tipo": "sobregiro",
                    "priority": "high" if uso > 0.9 else "warning",
                    "titulo": f"Sobregiro alto en {b['nombre']}",
                    "detalle": f"Uso: {uso*100:.1f}% · Disponible: ${b['saldo_efectivo']+b['sobregiro_asignado']-b['sobregiro_utilizado']:.2f}",
                    "fecha": today.isoformat(),
                })
        if b["saldo_efectivo"] < 1000:
            alerts.append({
                "id": f"sb-{b['id']}", "tipo": "saldo_bajo",
                "priority": "warning",
                "titulo": f"Saldo bajo en {b['nombre']}",
                "detalle": f"Saldo efectivo: ${b['saldo_efectivo']:.2f}",
                "fecha": today.isoformat(),
            })

    # Clientes pendientes (facturas > 30 días)
    facturas = await db.facturas.find({"estado": "pendiente"}, {"_id": 0}).to_list(2000)
    clientes = {c["id"]: c["nombre"] for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}
    for f in facturas:
        try:
            fe = datetime.fromisoformat(f["fecha_emision"]).date()
            dias = (today - fe).days
            if dias > 30:
                alerts.append({
                    "id": f"fc-{f['id']}", "tipo": "cliente_pendiente",
                    "priority": "high" if dias > 60 else "info",
                    "titulo": f"Factura vencida {dias} días",
                    "detalle": f"Cliente: {clientes.get(f['cliente_id'],'—')} · Doc: {f['numero_documento']}",
                    "fecha": f["fecha_emision"],
                })
        except Exception:
            pass

    priority_order = {"high": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: priority_order.get(a["priority"], 3))
    return alerts

@api.post("/alertas/enviar-email")
async def enviar_alertas_email(user: dict = Depends(require_role("admin", "financiero"))):
    als = await alertas(user)
    if not als:
        return {"sent": False, "reason": "Sin alertas"}
    rows = "".join([f"<tr><td style='padding:8px;border-bottom:1px solid #eee;'><b>{a['titulo']}</b><br/><span style='color:#666'>{a['detalle']}</span></td></tr>" for a in als[:20]])
    html = f"<h2>Resumen de Alertas Financieras</h2><table style='width:100%;border-collapse:collapse;font-family:sans-serif'>{rows}</table>"
    ok = await send_alert_email(user["email"], "Alertas Financieras · Resumen", html)
    return {"sent": ok, "count": len(als)}

# -----------------------------
# REPORTE EJECUTIVO SEMANAL (Viernes 18:00 hora Guayaquil)
# -----------------------------
TZ_EC = ZoneInfo("America/Guayaquil")

def _money(v: float) -> str:
    return f"${v:,.2f}"

async def build_weekly_report_html() -> dict:
    """Construye el HTML del Reporte Ejecutivo Semanal."""
    today = date.today()
    bancos = await db.bancos.find({}, {"_id": 0}).to_list(200)
    cheques = await db.cheques.find({}, {"_id": 0}).to_list(2000)
    facturas = await db.facturas.find({}, {"_id": 0}).to_list(2000)
    clientes = {c["id"]: c["nombre"] for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}
    flujo = await db.flujo.find({}, {"_id": 0}).to_list(2000)

    # KPIs
    saldo_total = sum(b["saldo_efectivo"] for b in bancos)
    sobregiro_disp = sum(b["sobregiro_asignado"] - b["sobregiro_utilizado"] for b in bancos)
    disponible = saldo_total + sobregiro_disp
    cheques_pend = [c for c in cheques if c["estado"] == "pendiente"]
    total_chq = sum(c["valor"] for c in cheques_pend)
    cartera = [f for f in facturas if f["estado"] == "pendiente"]
    total_cart = sum(f["subtotal"] - f["anticipos"] - f["retencion"] for f in cartera)
    total_ret = sum(f["retencion"] for f in facturas)

    # Cheques próximos 7 días
    proximos = []
    for c in cheques_pend:
        try:
            fc = datetime.fromisoformat(c["fecha_cobro"]).date()
            d = (fc - today).days
            if 0 <= d <= 7:
                proximos.append((d, c))
        except Exception:
            pass
    proximos.sort(key=lambda x: x[0])

    # Top morosos (>30 días)
    morosos_map = {}
    for f in cartera:
        try:
            fe = datetime.fromisoformat(f["fecha_emision"]).date()
            dias = (today - fe).days
            if dias > 30:
                nm = clientes.get(f["cliente_id"], "—")
                pendiente = f["subtotal"] - f["anticipos"] - f["retencion"]
                cur = morosos_map.get(nm, {"monto": 0.0, "dias_max": 0, "facturas": 0})
                cur["monto"] += pendiente
                cur["dias_max"] = max(cur["dias_max"], dias)
                cur["facturas"] += 1
                morosos_map[nm] = cur
        except Exception:
            pass
    morosos = sorted(morosos_map.items(), key=lambda x: -x[1]["monto"])[:10]

    # Semanas críticas (próximas 4 semanas) — egresos > ingresos
    semanas = []
    start = today
    for w in range(4):
        ws_start = start + timedelta(days=w * 7)
        ws_end = ws_start + timedelta(days=6)
        ws_in = sum(x["monto"] for x in flujo if x["tipo"] == "ingreso" and ws_start.isoformat() <= x["fecha"] <= ws_end.isoformat())
        ws_out = sum(x["monto"] for x in flujo if x["tipo"] == "egreso" and ws_start.isoformat() <= x["fecha"] <= ws_end.isoformat())
        ws_chq = sum(c["valor"] for c in cheques_pend if ws_start.isoformat() <= c.get("fecha_cobro", "") <= ws_end.isoformat())
        deficit = (ws_in) - (ws_out + ws_chq)
        semanas.append({
            "rango": f"{ws_start.strftime('%d %b')} – {ws_end.strftime('%d %b')}",
            "ingresos": ws_in, "egresos": ws_out + ws_chq, "neto": deficit,
            "critica": deficit < 0,
        })

    # HTML build
    kpi_card = lambda l, v, c="#0f172a": f"""
<td style="padding:14px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;width:33%;">
  <div style="font-size:10px;letter-spacing:1.5px;color:#64748b;text-transform:uppercase;font-weight:700">{l}</div>
  <div style="font-size:22px;font-weight:700;color:{c};margin-top:6px;font-family:Georgia,serif;">{v}</div>
</td>"""

    proximos_html = "".join([
        f"""<tr>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;">{c['numero']}</td>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;">{c['beneficiario']}</td>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;text-align:center;color:{'#dc2626' if d <= 2 else '#d97706'};font-weight:600">{d}d</td>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;text-align:right;font-weight:600">{_money(c['valor'])}</td>
        </tr>""" for d, c in proximos[:15]
    ]) or '<tr><td colspan="4" style="padding:14px;text-align:center;color:#94a3b8">Sin cheques en los próximos 7 días</td></tr>'

    morosos_html = "".join([
        f"""<tr>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;">{nm}</td>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;text-align:center">{m['facturas']}</td>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;text-align:center;color:#dc2626;font-weight:600">{m['dias_max']}d</td>
            <td style="padding:8px;border-bottom:1px solid #f1f5f9;text-align:right;font-weight:700">{_money(m['monto'])}</td>
        </tr>""" for nm, m in morosos
    ]) or '<tr><td colspan="4" style="padding:14px;text-align:center;color:#94a3b8">Sin clientes morosos</td></tr>'

    semanas_html = "".join([
        f"""<tr style="background:{'#fef2f2' if s['critica'] else '#f8fafc'}">
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;font-weight:600">{s['rango']} {'⚠️' if s['critica'] else ''}</td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:right;color:#15803d">{_money(s['ingresos'])}</td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:right;color:#b91c1c">{_money(s['egresos'])}</td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:right;font-weight:700;color:{'#dc2626' if s['critica'] else '#0f172a'}">{_money(s['neto'])}</td>
        </tr>""" for s in semanas
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
</div>
"""
    return {
        "html": html,
        "stats": {
            "saldo_total_bancos": round(saldo_total, 2),
            "disponible_real": round(disponible, 2),
            "total_cheques_pendientes": round(total_chq, 2),
            "cartera_pendiente": round(total_cart, 2),
            "total_retenciones": round(total_ret, 2),
            "cheques_proximos": len(proximos),
            "morosos": len(morosos),
            "semanas_criticas": sum(1 for s in semanas if s["critica"]),
        },
    }

async def send_weekly_report() -> dict:
    """Envía el reporte ejecutivo a admins y financieros."""
    report = await build_weekly_report_html()
    recipients = await db.users.find({"role": {"$in": ["admin", "financiero"]}}, {"_id": 0, "email": 1}).to_list(100)
    emails = [r["email"] for r in recipients if r.get("email")]
    if not emails:
        return {"sent": False, "reason": "Sin destinatarios", "stats": report["stats"]}
    subject = f"Reporte Ejecutivo Semanal · {date.today().strftime('%d %b %Y')}"
    sent_count = 0
    for em in emails:
        ok = await send_alert_email(em, subject, report["html"])
        if ok:
            sent_count += 1
    logger.info(f"Reporte semanal: enviados {sent_count}/{len(emails)} · stats={report['stats']}")
    return {"sent": sent_count > 0, "recipients": emails, "delivered": sent_count, "stats": report["stats"]}

@api.post("/reportes/semanal/enviar")
async def trigger_weekly_report(user: dict = Depends(require_role("admin", "financiero"))):
    """Envío manual del reporte ejecutivo (para pruebas, sin esperar al viernes)."""
    return await send_weekly_report()

@api.get("/reportes/semanal/preview")
async def preview_weekly_report(user: dict = Depends(get_current_user)):
    """Devuelve sólo las estadísticas (sin enviar)."""
    r = await build_weekly_report_html()
    return r["stats"]

# Schedule config (día/hora del reporte semanal) -----------------
DAY_NAMES = {0: "lun", 1: "mar", 2: "mié", 3: "jue", 4: "vie", 5: "sáb", 6: "dom"}
DAY_NAMES_FULL = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
CRON_DAYS = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}

class ScheduleConfig(BaseModel):
    day_of_week: int  # 0=Lun ... 6=Dom
    hour: int  # 0-23
    minute: int = 0

async def _get_schedule_config() -> dict:
    """Lee config desde MongoDB (o default viernes 18:00)."""
    cfg = await db.settings.find_one({"key": "weekly_report"}, {"_id": 0})
    if not cfg:
        return {"day_of_week": 4, "hour": 18, "minute": 0}
    return {"day_of_week": cfg.get("day_of_week", 4), "hour": cfg.get("hour", 18), "minute": cfg.get("minute", 0)}

def _reschedule_weekly_report(cfg: dict):
    if scheduler is None:
        return
    cron = CronTrigger(
        day_of_week=CRON_DAYS[cfg["day_of_week"]],
        hour=cfg["hour"],
        minute=cfg["minute"],
        timezone=TZ_EC,
    )
    scheduler.reschedule_job("reporte_semanal", trigger=cron)

@api.get("/reportes/semanal/config")
async def get_schedule_config(user: dict = Depends(get_current_user)):
    cfg = await _get_schedule_config()
    job = scheduler.get_job("reporte_semanal") if scheduler else None
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {
        **cfg,
        "day_label": DAY_NAMES_FULL[cfg["day_of_week"]],
        "next_run": next_run,
        "timezone": "America/Guayaquil",
    }

@api.put("/reportes/semanal/config")
async def update_schedule_config(body: ScheduleConfig, user: dict = Depends(require_role("admin"))):
    if not (0 <= body.day_of_week <= 6):
        raise HTTPException(400, "day_of_week debe ser 0-6")
    if not (0 <= body.hour <= 23):
        raise HTTPException(400, "hour debe ser 0-23")
    if not (0 <= body.minute <= 59):
        raise HTTPException(400, "minute debe ser 0-59")
    new_cfg = {"day_of_week": body.day_of_week, "hour": body.hour, "minute": body.minute}
    await db.settings.update_one(
        {"key": "weekly_report"},
        {"$set": {**new_cfg, "key": "weekly_report", "updated_at": iso(now_utc())}},
        upsert=True,
    )
    _reschedule_weekly_report(new_cfg)
    job = scheduler.get_job("reporte_semanal")
    return {
        **new_cfg,
        "day_label": DAY_NAMES_FULL[body.day_of_week],
        "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
        "timezone": "America/Guayaquil",
    }

# -----------------------------
# EXPORT EXCEL
# -----------------------------
def _excel_response(wb: Workbook, filename: str) -> StreamingResponse:
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@api.get("/export/{modulo}")
async def export_excel(modulo: str, user: dict = Depends(get_current_user)):
    wb = Workbook()
    ws = wb.active
    if modulo == "cheques":
        ws.title = "Cheques"
        bancos = {b["id"]: b["nombre"] for b in await db.bancos.find({}, {"_id": 0}).to_list(200)}
        ws.append(["Banco", "Número", "Valor", "Beneficiario", "Fecha Emisión", "Fecha Cobro", "Estado", "Motivo"])
        for c in await db.cheques.find({}, {"_id": 0}).sort([("banco_id", 1), ("fecha_cobro", 1)]).to_list(2000):
            ws.append([bancos.get(c.get("banco_id"), "—"), c["numero"], c["valor"], c["beneficiario"], c["fecha_emision"], c["fecha_cobro"], c["estado"], c.get("motivo", "")])
    elif modulo == "cartera":
        ws.title = "Cartera"
        clientes = {c["id"]: c["nombre"] for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}
        ws.append(["Cliente", "Documento", "Fecha", "Estado", "Subtotal", "Anticipos", "Retención", "Total"])
        for f in await db.facturas.find({}, {"_id": 0}).to_list(2000):
            t = f["subtotal"] - f["anticipos"] - f["retencion"]
            ws.append([clientes.get(f["cliente_id"], "—"), f["numero_documento"], f["fecha_emision"], f["estado"], f["subtotal"], f["anticipos"], f["retencion"], round(t, 2)])
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

# -----------------------------
# EXPORT PDF
# -----------------------------
NAVY = colors.HexColor("#0f172a")
TEAL = colors.HexColor("#0f766e")
SLATE_50 = colors.HexColor("#f8fafc")
SLATE_200 = colors.HexColor("#e2e8f0")
SLATE_500 = colors.HexColor("#64748b")
AMBER = colors.HexColor("#b45309")
BLUE = colors.HexColor("#1e40af")

def _pdf_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=20, leading=24, textColor=NAVY, spaceAfter=4),
        "subtitle": ParagraphStyle("sub", parent=base["Normal"], fontSize=9, textColor=SLATE_500, spaceAfter=16),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, textColor=NAVY, spaceBefore=14, spaceAfter=8),
        "small": ParagraphStyle("sm", parent=base["Normal"], fontSize=8, textColor=SLATE_500),
        "overline": ParagraphStyle("ov", parent=base["Normal"], fontSize=7, textColor=SLATE_500, spaceAfter=2),
        "kpi": ParagraphStyle("kpi", parent=base["Normal"], fontSize=14, textColor=NAVY, fontName="Helvetica-Bold"),
    }

def _header_paragraphs(title: str, subtitle: str = "") -> list:
    st = _pdf_styles()
    sub = subtitle or f"Generado: {datetime.now(TZ_EC).strftime('%d %b %Y · %H:%M')} (Ecuador)"
    return [
        Paragraph("TESORERÍA · CONTROL FINANCIERO", st["overline"]),
        Paragraph(title, st["title"]),
        Paragraph(sub, st["subtitle"]),
    ]

def _table_style(header_bg=NAVY, header_color=colors.white) -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), header_color),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, SLATE_200),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SLATE_50]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ])

def _pdf_response(elements: list, filename: str, landscape_mode: bool = False) -> StreamingResponse:
    buf = BytesIO()
    page = landscape(A4) if landscape_mode else A4
    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title=filename)
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

@api.get("/export/pdf/{modulo}")
async def export_pdf(modulo: str, user: dict = Depends(get_current_user)):
    st = _pdf_styles()
    elements: list = []

    if modulo == "cheques":
        elements += _header_paragraphs("Estado de Cheques Emitidos")
        bancos = {b["id"]: b["nombre"] for b in await db.bancos.find({}, {"_id": 0}).to_list(200)}
        rows = [["Banco", "N°", "Beneficiario", "Emisión", "Cobro", "Valor", "Estado"]]
        items = await db.cheques.find({}, {"_id": 0}).sort([("banco_id", 1), ("fecha_cobro", 1)]).to_list(2000)
        total = 0.0
        for c in items:
            rows.append([
                bancos.get(c.get("banco_id"), "—"), c["numero"], c["beneficiario"][:28],
                c["fecha_emision"], c["fecha_cobro"], _fmt_money(c["valor"]), c["estado"].capitalize(),
            ])
            if c["estado"] == "pendiente":
                total += c["valor"]
        t = Table(rows, repeatRows=1, colWidths=[32*mm, 22*mm, 55*mm, 22*mm, 22*mm, 24*mm, 22*mm])
        t.setStyle(_table_style())
        elements.append(t)
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>Total pendiente de cobro:</b> {_fmt_money(total)} · {len(items)} cheques", st["small"]))
        return _pdf_response(elements, "cheques.pdf", landscape_mode=True)

    if modulo == "cartera":
        elements += _header_paragraphs("Cartera de Clientes")
        clientes = {c["id"]: c["nombre"] for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}
        rows = [["Cliente", "Documento", "Fecha", "Subtotal", "Anticipos", "Retención", "Total", "Estado"]]
        items = await db.facturas.find({}, {"_id": 0}).sort("fecha_emision", -1).to_list(2000)
        total_pend = 0.0
        for f in items:
            tot = f["subtotal"] - f["anticipos"] - f["retencion"]
            rows.append([
                clientes.get(f["cliente_id"], "—")[:28], f["numero_documento"],
                f["fecha_emision"], _fmt_money(f["subtotal"]), _fmt_money(f["anticipos"]),
                _fmt_money(f["retencion"]), _fmt_money(tot), f["estado"].capitalize(),
            ])
            if f["estado"] == "pendiente":
                total_pend += tot
        t = Table(rows, repeatRows=1, colWidths=[50*mm, 22*mm, 22*mm, 22*mm, 22*mm, 22*mm, 24*mm, 22*mm])
        t.setStyle(_table_style())
        elements.append(t)
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>Total cartera pendiente:</b> {_fmt_money(total_pend)}", st["small"]))
        return _pdf_response(elements, "cartera.pdf", landscape_mode=True)

    if modulo == "retenciones":
        elements += _header_paragraphs("Consolidado de Retenciones")
        clientes = {c["id"]: c["nombre"] for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}
        items = await db.facturas.find({"retencion": {"$gt": 0}}, {"_id": 0}).to_list(2000)
        rows = [["Cliente", "Documento", "Fecha", "Valor Retenido"]]
        total = 0.0
        for f in items:
            rows.append([
                clientes.get(f["cliente_id"], "—"), f["numero_documento"],
                f["fecha_emision"], _fmt_money(f["retencion"]),
            ])
            total += f["retencion"]
        t = Table(rows, repeatRows=1, colWidths=[75*mm, 35*mm, 30*mm, 34*mm])
        t.setStyle(_table_style())
        elements.append(t)
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>Total general retenciones:</b> {_fmt_money(total)}", st["small"]))
        return _pdf_response(elements, "retenciones.pdf")

    if modulo == "bancos":
        elements += _header_paragraphs("Movimientos y Posición Bancaria")
        bancos = await db.bancos.find({}, {"_id": 0}).to_list(200)
        rows = [["Banco", "Saldo", "Sobregiro Asig.", "Sobregiro Usado", "Disponible"]]
        tot_saldo = tot_disp = 0.0
        for b in bancos:
            disp = b["saldo_efectivo"] + b["sobregiro_asignado"] - b["sobregiro_utilizado"]
            rows.append([b["nombre"], _fmt_money(b["saldo_efectivo"]), _fmt_money(b["sobregiro_asignado"]), _fmt_money(b["sobregiro_utilizado"]), _fmt_money(disp)])
            tot_saldo += b["saldo_efectivo"]
            tot_disp += disp
        t = Table(rows, repeatRows=1, colWidths=[50*mm, 30*mm, 32*mm, 32*mm, 30*mm])
        t.setStyle(_table_style())
        elements.append(t)
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>Saldo consolidado:</b> {_fmt_money(tot_saldo)} · <b>Disponible real:</b> {_fmt_money(tot_disp)}", st["small"]))
        return _pdf_response(elements, "bancos.pdf")

    if modulo == "flujo":
        elements += _header_paragraphs("Flujo Financiero")
        bancos = {b["id"]: b["nombre"] for b in await db.bancos.find({}, {"_id": 0}).to_list(200)}
        items = await db.flujo.find({}, {"_id": 0}).sort("fecha", 1).to_list(2000)
        rows = [["Fecha", "Tipo", "Descripción", "Banco", "Monto"]]
        tot_in = tot_out = 0.0
        for x in items:
            rows.append([x["fecha"], x["tipo"].capitalize(), x["descripcion"][:38], bancos.get(x.get("banco_id"), "—"), _fmt_money(x["monto"])])
            if x["tipo"] == "ingreso":
                tot_in += x["monto"]
            else:
                tot_out += x["monto"]
        t = Table(rows, repeatRows=1, colWidths=[28*mm, 22*mm, 70*mm, 40*mm, 24*mm])
        t.setStyle(_table_style())
        elements.append(t)
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(
            f"<b>Ingresos:</b> {_fmt_money(tot_in)} · <b>Egresos:</b> {_fmt_money(tot_out)} · <b>Neto:</b> {_fmt_money(tot_in - tot_out)}",
            st["small"],
        ))
        return _pdf_response(elements, "flujo.pdf", landscape_mode=True)

    if modulo == "gerencial":
        # Reporte ejecutivo: KPIs + tablas resumen
        elements += _header_paragraphs("Reporte Gerencial Consolidado")
        bancos = await db.bancos.find({}, {"_id": 0}).to_list(200)
        cheques = await db.cheques.find({}, {"_id": 0}).to_list(2000)
        facturas = await db.facturas.find({}, {"_id": 0}).to_list(2000)
        clientes = {c["id"]: c["nombre"] for c in await db.clientes.find({}, {"_id": 0}).to_list(500)}

        saldo = sum(b["saldo_efectivo"] for b in bancos)
        disp = saldo + sum(b["sobregiro_asignado"] - b["sobregiro_utilizado"] for b in bancos)
        chq_pend = sum(c["valor"] for c in cheques if c["estado"] == "pendiente")
        cart_pend = sum(f["subtotal"] - f["anticipos"] - f["retencion"] for f in facturas if f["estado"] == "pendiente")
        ret_total = sum(f["retencion"] for f in facturas)

        kpi_rows = [
            ["INDICADOR", "VALOR"],
            ["Saldo consolidado bancos", _fmt_money(saldo)],
            ["Disponible real (con sobregiro)", _fmt_money(disp)],
            ["Cheques pendientes de cobro", _fmt_money(chq_pend)],
            ["Cartera pendiente por cobrar", _fmt_money(cart_pend)],
            ["Total retenciones aplicadas", _fmt_money(ret_total)],
        ]
        t = Table(kpi_rows, colWidths=[110*mm, 60*mm])
        t.setStyle(_table_style())
        elements.append(t)

        # Posición bancaria
        elements.append(Paragraph("Posición bancaria", st["h2"]))
        b_rows = [["Banco", "Saldo", "Sobregiro Usado", "Disponible"]]
        for b in bancos:
            d = b["saldo_efectivo"] + b["sobregiro_asignado"] - b["sobregiro_utilizado"]
            b_rows.append([b["nombre"], _fmt_money(b["saldo_efectivo"]), _fmt_money(b["sobregiro_utilizado"]), _fmt_money(d)])
        tb = Table(b_rows, repeatRows=1, colWidths=[60*mm, 36*mm, 40*mm, 34*mm])
        tb.setStyle(_table_style(header_bg=TEAL))
        elements.append(tb)

        # Top 5 cartera pendiente por cliente
        elements.append(Paragraph("Top 5 clientes con mayor cartera pendiente", st["h2"]))
        bucket = {}
        for f in facturas:
            if f["estado"] != "pendiente":
                continue
            nm = clientes.get(f["cliente_id"], "—")
            bucket[nm] = bucket.get(nm, 0) + (f["subtotal"] - f["anticipos"] - f["retencion"])
        top = sorted(bucket.items(), key=lambda x: -x[1])[:5]
        c_rows = [["Cliente", "Pendiente"]] + [[nm, _fmt_money(v)] for nm, v in top]
        if len(c_rows) == 1:
            c_rows.append(["Sin cartera pendiente", "—"])
        tc = Table(c_rows, repeatRows=1, colWidths=[120*mm, 50*mm])
        tc.setStyle(_table_style(header_bg=BLUE))
        elements.append(tc)

        elements.append(Spacer(1, 14))
        elements.append(Paragraph("Documento generado automáticamente por el Sistema Integral de Control Financiero.", st["small"]))
        return _pdf_response(elements, "reporte_gerencial.pdf")

    raise HTTPException(400, "Módulo inválido")

# -----------------------------
# SEED
# -----------------------------
async def seed_users():
    seeds = [
        (os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"], "Administrador", "admin"),
        (os.environ["FINANCIERO_EMAIL"], os.environ["FINANCIERO_PASSWORD"], "Financiero Demo", "financiero"),
        (os.environ["CONSULTA_EMAIL"], os.environ["CONSULTA_PASSWORD"], "Consulta Demo", "consulta"),
    ]
    for email, pw, name, role in seeds:
        email = email.lower()
        existing = await db.users.find_one({"email": email})
        if not existing:
            await db.users.insert_one({
                "id": new_id(), "email": email, "password_hash": hash_password(pw),
                "name": name, "role": role, "created_at": iso(now_utc())
            })
        elif not verify_password(pw, existing["password_hash"]):
            await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(pw), "role": role}})

async def seed_demo():
    if await db.bancos.count_documents({}) > 0:
        return
    from seed_data import BANCOS, CLIENTES, CHEQUES, FACTURAS, FLUJO
    bancos_ids = {}
    for name, data in BANCOS.items():
        bid = new_id()
        bancos_ids[name] = bid
        await db.bancos.insert_one({"id": bid, "nombre": name, "created_at": iso(now_utc()), **data})
    clientes_ids = {}
    for cli in CLIENTES:
        cid = new_id()
        clientes_ids[cli["nombre"]] = cid
        await db.clientes.insert_one({"id": cid, "created_at": iso(now_utc()), **cli})
    for ch in CHEQUES:
        bid = bancos_ids[ch.pop("banco_nombre")]
        await db.cheques.insert_one({"id": new_id(), "banco_id": bid, "created_at": iso(now_utc()), **ch})
    for f in FACTURAS:
        cid = clientes_ids[f.pop("cliente_nombre")]
        await db.facturas.insert_one({"id": new_id(), "cliente_id": cid, "created_at": iso(now_utc()), **f})
    for x in FLUJO:
        bid = bancos_ids.get(x.pop("banco_nombre", None)) if x.get("banco_nombre") else None
        await db.flujo.insert_one({"id": new_id(), "banco_id": bid, "created_at": iso(now_utc()), **x})

@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.bancos.create_index("id", unique=True)
    await db.cheques.create_index("id", unique=True)
    await db.clientes.create_index("id", unique=True)
    await db.facturas.create_index("id", unique=True)
    await db.flujo.create_index("id", unique=True)
    await seed_users()
    await seed_demo()

    # Scheduler: lee config persistida (default viernes 18:00 hora Ecuador)
    global scheduler
    cfg = await _get_schedule_config()
    scheduler = AsyncIOScheduler(timezone=TZ_EC)
    scheduler.add_job(
        send_weekly_report,
        CronTrigger(
            day_of_week=CRON_DAYS[cfg["day_of_week"]],
            hour=cfg["hour"],
            minute=cfg["minute"],
            timezone=TZ_EC,
        ),
        id="reporte_semanal",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    next_run = scheduler.get_job("reporte_semanal").next_run_time
    logger.info(f"Reporte semanal · {DAY_NAMES_FULL[cfg['day_of_week']]} {cfg['hour']:02d}:{cfg['minute']:02d} EC · próxima: {next_run}")
    # Escribir credenciales de prueba
    try:
        os.makedirs("/app/memory", exist_ok=True)
        with open("/app/memory/test_credentials.md", "w") as f:
            f.write(f"""# Credenciales de prueba

## Usuarios sembrados

| Rol | Email | Contraseña |
|---|---|---|
| admin | {os.environ['ADMIN_EMAIL']} | {os.environ['ADMIN_PASSWORD']} |
| financiero | {os.environ['FINANCIERO_EMAIL']} | {os.environ['FINANCIERO_PASSWORD']} |
| consulta | {os.environ['CONSULTA_EMAIL']} | {os.environ['CONSULTA_PASSWORD']} |

## Endpoints de auth
- POST /api/auth/login
- POST /api/auth/register
- POST /api/auth/logout
- GET /api/auth/me
""")
    except Exception as e:
        logger.error(f"test_credentials error: {e}")

@app.on_event("shutdown")
async def on_shutdown():
    try:
        if "scheduler" in globals() and scheduler.running:
            scheduler.shutdown(wait=False)
    except Exception:
        pass
    client.close()

# Mount router
app.include_router(api)

frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
allowed = [frontend_url, "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
