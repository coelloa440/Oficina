"""
Punto de entrada de la aplicación.
"""
from dotenv import load_dotenv
from pathlib import Path
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from zoneinfo import ZoneInfo

import database
from core import hash_password, verify_password, new_id, iso, now_utc
from services.email import init_resend
from services.reports import send_weekly_report
from routers import auth, bancos, clientes, cheques, facturas, flujo, dashboard, alertas, reportes, exports, auditoria
from routers.reportes import set_scheduler

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TZ_EC = ZoneInfo("America/Guayaquil")
CRON_DAYS = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
DAY_NAMES = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}

app = FastAPI(title="Sistema Integral de Control Financiero y Cartera")

PREFIX = "/api"
app.include_router(auth.router, prefix=PREFIX)
app.include_router(bancos.router, prefix=PREFIX)
app.include_router(auditoria.router, prefix=PREFIX)
app.include_router(clientes.router, prefix=PREFIX)
app.include_router(cheques.router, prefix=PREFIX)
app.include_router(facturas.router, prefix=PREFIX)
app.include_router(flujo.router, prefix=PREFIX)
app.include_router(dashboard.router, prefix=PREFIX)
app.include_router(alertas.router, prefix=PREFIX)
app.include_router(reportes.router, prefix=PREFIX)
app.include_router(exports.router, prefix=PREFIX)
frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _seed_users():
    db = database.get_db()
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
                "id": new_id(),
                "email": email,
                "password_hash": hash_password(pw),
                "name": name,
                "role": role,
                "created_at": iso(now_utc()),
            })
        elif not verify_password(pw, existing["password_hash"]):
            await db.users.update_one(
                {"email": email},
                {"$set": {"password_hash": hash_password(pw), "role": role}},
            )


async def _seed_demo():
    db = database.get_db()

    if await db.bancos.count_documents({}) > 0:
        return

    from seed_data import BANCOS, CLIENTES, CHEQUES, FACTURAS, FLUJO

    bancos_ids = {}
    clientes_ids = {}

    for name, data in BANCOS.items():
        bid = new_id()
        bancos_ids[name] = bid
        await db.bancos.insert_one({"id": bid, "nombre": name, "created_at": iso(now_utc()), **data})

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


async def _write_test_credentials():
    try:
        memory_dir = ROOT_DIR / "memory"
        memory_dir.mkdir(exist_ok=True)

        with open(memory_dir / "test_credentials.md", "w", encoding="utf-8") as f:
            f.write(f"""# Credenciales de prueba

| Rol | Email | Contraseña |
|---|---|---|
| admin | {os.environ['ADMIN_EMAIL']} | {os.environ['ADMIN_PASSWORD']} |
| financiero | {os.environ['FINANCIERO_EMAIL']} | {os.environ['FINANCIERO_PASSWORD']} |
| consulta | {os.environ['CONSULTA_EMAIL']} | {os.environ['CONSULTA_PASSWORD']} |
""")
    except Exception as e:
        logger.error(f"test_credentials error: {e}")


@app.on_event("startup")
async def on_startup():
    db = database.init_db()

    await db.users.create_index("email", unique=True)
    await db.bancos.create_index("id", unique=True)
    await db.cheques.create_index("id", unique=True)
    await db.clientes.create_index("id", unique=True)
    await db.facturas.create_index("id", unique=True)
    await db.flujo.create_index("id", unique=True)

    await _seed_users()
    await _seed_demo()

    init_resend()

    cfg = await _get_schedule_cfg(db)
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
    set_scheduler(scheduler)

    next_run = scheduler.get_job("reporte_semanal").next_run_time
    logger.info(
        f"Reporte semanal · {DAY_NAMES[cfg['day_of_week']]} "
        f"{cfg['hour']:02d}:{cfg['minute']:02d} EC · próxima: {next_run}"
    )

    await _write_test_credentials()


@app.on_event("shutdown")
async def on_shutdown():
    from routers.reportes import _scheduler

    try:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
    except Exception:
        pass

    database.close_db()


async def _get_schedule_cfg(db) -> dict:
    cfg = await db.settings.find_one({"key": "weekly_report"}, {"_id": 0})
    if not cfg:
        return {"day_of_week": 4, "hour": 18, "minute": 0}

    return {
        "day_of_week": cfg.get("day_of_week", 4),
        "hour": cfg.get("hour", 18),
        "minute": cfg.get("minute", 0),
    }