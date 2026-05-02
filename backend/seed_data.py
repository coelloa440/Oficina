"""Datos demo iniciales para el Sistema Financiero."""
from datetime import date, timedelta

today = date.today()


def _d(offset):
    return (today + timedelta(days=offset)).isoformat()


BANCOS = {
    "Banco Guayaquil": {
        "saldo_efectivo": 45200.75,
        "sobregiro_asignado": 20000.0,
        "sobregiro_utilizado": 5000.0,
        "color": "#0f766e",
    },
    "Banco Bolivariano": {
        "saldo_efectivo": 18550.30,
        "sobregiro_asignado": 15000.0,
        "sobregiro_utilizado": 11800.0,
        "color": "#1e40af",
    },
    "Banco Pichincha": {
        "saldo_efectivo": 820.50,
        "sobregiro_asignado": 10000.0,
        "sobregiro_utilizado": 2000.0,
        "color": "#b91c1c",
    },
}

CLIENTES = [
    {"nombre": "Distribuidora Andina S.A.", "ruc": "1790012345001", "contacto": "María López", "email": "mlopez@andina.com"},
    {"nombre": "Comercial Pacífico Cía. Ltda.", "ruc": "0992345678001", "contacto": "Pedro Suárez", "email": "psuarez@pacifico.ec"},
    {"nombre": "Ferretería El Constructor", "ruc": "1792234567001", "contacto": "Luis Cevallos", "email": "luis@constructor.ec"},
    {"nombre": "AgroExport Ecuador", "ruc": "0992876543001", "contacto": "Ana Moreira", "email": "amoreira@agroexport.ec"},
    {"nombre": "Tech Solutions S.A.", "ruc": "1791098765001", "contacto": "Carlos Vera", "email": "cvera@techsol.ec"},
    {"nombre": "Alimentos Frescos del Sur", "ruc": "0993456789001", "contacto": "Rosa Mendoza", "email": "rmendoza@fsur.ec"},
]

CHEQUES = [
    {"numero": "001-2345", "valor": 5200.00, "beneficiario": "Proveedor Alfa S.A.", "fecha_emision": _d(-5), "fecha_cobro": _d(2), "motivo": "Compra de materia prima", "estado": "pendiente", "banco_nombre": "Banco Guayaquil"},
    {"numero": "001-2346", "valor": 1850.50, "beneficiario": "Transportes Veloz", "fecha_emision": _d(-10), "fecha_cobro": _d(-1), "motivo": "Servicio de flete", "estado": "cobrado", "banco_nombre": "Banco Guayaquil"},
    {"numero": "002-0891", "valor": 8900.00, "beneficiario": "Imp. Norte Ltda.", "fecha_emision": _d(-3), "fecha_cobro": _d(5), "motivo": "Importación equipos", "estado": "pendiente", "banco_nombre": "Banco Bolivariano"},
    {"numero": "002-0892", "valor": 420.00, "beneficiario": "Cía. Eléctrica", "fecha_emision": _d(-20), "fecha_cobro": _d(-15), "motivo": "Servicios básicos", "estado": "cobrado", "banco_nombre": "Banco Bolivariano"},
    {"numero": "003-0145", "valor": 3200.00, "beneficiario": "Seguros del Pacífico", "fecha_emision": _d(-2), "fecha_cobro": _d(12), "motivo": "Prima anual", "estado": "pendiente", "banco_nombre": "Banco Pichincha"},
    {"numero": "001-2347", "valor": 1100.00, "beneficiario": "Arriendo Local", "fecha_emision": _d(-1), "fecha_cobro": _d(1), "motivo": "Arriendo mes", "estado": "pendiente", "banco_nombre": "Banco Guayaquil"},
    {"numero": "003-0146", "valor": 6500.00, "beneficiario": "Maquinarias SCJ", "fecha_emision": _d(-30), "fecha_cobro": _d(-25), "motivo": "Repuestos", "estado": "anulado", "banco_nombre": "Banco Pichincha"},
    {"numero": "002-0893", "valor": 950.75, "beneficiario": "Publicidad Digital", "fecha_emision": _d(-7), "fecha_cobro": _d(4), "motivo": "Campaña redes", "estado": "pendiente", "banco_nombre": "Banco Bolivariano"},
    {"numero": "001-2348", "valor": 2380.00, "beneficiario": "Suministros Oficina", "fecha_emision": _d(-4), "fecha_cobro": _d(7), "motivo": "Útiles", "estado": "pendiente", "banco_nombre": "Banco Guayaquil"},
    {"numero": "003-0147", "valor": 15000.00, "beneficiario": "Constructora RJ", "fecha_emision": _d(-1), "fecha_cobro": _d(14), "motivo": "Remodelación", "estado": "pendiente", "banco_nombre": "Banco Pichincha"},
]

FACTURAS = [
    {"cliente_nombre": "Distribuidora Andina S.A.", "numero_documento": "F-0001", "fecha_emision": _d(-45), "estado": "pendiente", "subtotal": 12000.00, "anticipos": 2000.00, "retencion": 120.00},
    {"cliente_nombre": "Distribuidora Andina S.A.", "numero_documento": "F-0002", "fecha_emision": _d(-20), "estado": "pendiente", "subtotal": 8500.00, "anticipos": 0.00, "retencion": 85.00},
    {"cliente_nombre": "Comercial Pacífico Cía. Ltda.", "numero_documento": "F-0003", "fecha_emision": _d(-15), "estado": "pendiente", "subtotal": 4200.00, "anticipos": 500.00, "retencion": 42.00},
    {"cliente_nombre": "Comercial Pacífico Cía. Ltda.", "numero_documento": "F-0004", "fecha_emision": _d(-70), "estado": "pendiente", "subtotal": 9800.00, "anticipos": 1000.00, "retencion": 98.00},
    {"cliente_nombre": "Ferretería El Constructor", "numero_documento": "F-0005", "fecha_emision": _d(-5), "estado": "pendiente", "subtotal": 1850.00, "anticipos": 0.00, "retencion": 18.50},
    {"cliente_nombre": "AgroExport Ecuador", "numero_documento": "F-0006", "fecha_emision": _d(-35), "estado": "pendiente", "subtotal": 22000.00, "anticipos": 5000.00, "retencion": 220.00},
    {"cliente_nombre": "AgroExport Ecuador", "numero_documento": "F-0007", "fecha_emision": _d(-90), "estado": "recibida", "subtotal": 15000.00, "anticipos": 0.00, "retencion": 150.00},
    {"cliente_nombre": "Tech Solutions S.A.", "numero_documento": "F-0008", "fecha_emision": _d(-10), "estado": "pendiente", "subtotal": 6500.00, "anticipos": 1500.00, "retencion": 65.00},
    {"cliente_nombre": "Tech Solutions S.A.", "numero_documento": "F-0009", "fecha_emision": _d(-55), "estado": "pendiente", "subtotal": 3200.00, "anticipos": 0.00, "retencion": 32.00},
    {"cliente_nombre": "Alimentos Frescos del Sur", "numero_documento": "F-0010", "fecha_emision": _d(-25), "estado": "pendiente", "subtotal": 5400.00, "anticipos": 800.00, "retencion": 54.00},
    {"cliente_nombre": "Alimentos Frescos del Sur", "numero_documento": "F-0011", "fecha_emision": _d(-2), "estado": "pendiente", "subtotal": 7200.00, "anticipos": 0.00, "retencion": 72.00},
    {"cliente_nombre": "Distribuidora Andina S.A.", "numero_documento": "F-0012", "fecha_emision": _d(-100), "estado": "recibida", "subtotal": 10500.00, "anticipos": 2500.00, "retencion": 105.00},
]

FLUJO = [
    {"fecha": _d(0), "tipo": "egreso", "descripcion": "Pago proveedor Alfa", "monto": 5200.00, "banco_nombre": "Banco Guayaquil"},
    {"fecha": _d(1), "tipo": "egreso", "descripcion": "Arriendo local", "monto": 1100.00, "banco_nombre": "Banco Guayaquil"},
    {"fecha": _d(2), "tipo": "egreso", "descripcion": "Nómina parcial", "monto": 8400.00, "banco_nombre": "Banco Bolivariano"},
    {"fecha": _d(2), "tipo": "ingreso", "descripcion": "Cobranza cliente Andina", "monto": 9980.00, "banco_nombre": "Banco Guayaquil"},
    {"fecha": _d(3), "tipo": "egreso", "descripcion": "Pago SRI", "monto": 3200.00, "banco_nombre": "Banco Bolivariano"},
    {"fecha": _d(4), "tipo": "egreso", "descripcion": "Pub. Digital", "monto": 950.75, "banco_nombre": "Banco Bolivariano"},
    {"fecha": _d(4), "tipo": "ingreso", "descripcion": "Cobranza Tech Solutions", "monto": 4935.00, "banco_nombre": "Banco Guayaquil"},
    {"fecha": _d(5), "tipo": "egreso", "descripcion": "Importación equipos", "monto": 8900.00, "banco_nombre": "Banco Bolivariano"},
    {"fecha": _d(6), "tipo": "ingreso", "descripcion": "Cobranza AgroExport", "monto": 16780.00, "banco_nombre": "Banco Guayaquil"},
]
