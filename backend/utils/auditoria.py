from datetime import datetime, timezone
from database import get_db


async def log_event(usuario: str, modulo: str, accion: str, detalle: str):
    db = get_db()

    await db.auditoria.insert_one({
        "usuario": usuario,
        "modulo": modulo,
        "accion": accion,
        "detalle": detalle,
        "fecha": datetime.now(timezone.utc).isoformat()
    })