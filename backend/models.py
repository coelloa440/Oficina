"""Modelos Pydantic compartidos por todos los routers."""
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr


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
    fecha_emision: str   # ISO date
    fecha_cobro: str     # ISO date
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
    fecha: str   # ISO date
    tipo: Literal["ingreso", "egreso"]
    descripcion: str
    monto: float
    banco_id: Optional[str] = None


class ScheduleConfig(BaseModel):
    day_of_week: int   # 0=Lun … 6=Dom
    hour: int          # 0-23
    minute: int = 0
