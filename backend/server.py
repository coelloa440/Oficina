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
async def delete_banco(banco_id: str, user: dict = Depends(require_role("admin"))):
    await db.bancos.delete_one({"id": banco_id})
    return {"ok": True}

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
    return [_cheque_enrich(c) for c in items]

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
        ws.append(["Número", "Valor", "Beneficiario", "Fecha Emisión", "Fecha Cobro", "Estado", "Motivo"])
        for c in await db.cheques.find({}, {"_id": 0}).to_list(2000):
            ws.append([c["numero"], c["valor"], c["beneficiario"], c["fecha_emision"], c["fecha_cobro"], c["estado"], c.get("motivo", "")])
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
