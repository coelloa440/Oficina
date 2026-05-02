"""Router de reportes: configuración del scheduler y envío manual."""
import logging
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, Depends, HTTPException

from core import get_current_user, require_role, iso, now_utc
from database import get_db
from models import ScheduleConfig
from services.reports import build_weekly_report_html, send_weekly_report

logger  = logging.getLogger(__name__)
TZ_EC   = ZoneInfo("America/Guayaquil")
router  = APIRouter(prefix="/reportes", tags=["reportes"])

# Referencia al scheduler (inyectada desde server.py al arrancar)
_scheduler = None

DAY_NAMES_FULL = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
CRON_DAYS      = {0: "mon",   1: "tue",    2: "wed",       3: "thu",   4: "fri",    5: "sat",    6: "sun"}


def set_scheduler(scheduler):
    global _scheduler
    _scheduler = scheduler


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

async def _get_schedule_config() -> dict:
    db  = get_db()
    cfg = await db.settings.find_one({"key": "weekly_report"}, {"_id": 0})
    if not cfg:
        return {"day_of_week": 4, "hour": 18, "minute": 0}
    return {"day_of_week": cfg.get("day_of_week", 4), "hour": cfg.get("hour", 18), "minute": cfg.get("minute", 0)}


def _reschedule(cfg: dict):
    if _scheduler is None:
        return
    cron = CronTrigger(
        day_of_week=CRON_DAYS[cfg["day_of_week"]],
        hour=cfg["hour"],
        minute=cfg["minute"],
        timezone=TZ_EC,
    )
    _scheduler.reschedule_job("reporte_semanal", trigger=cron)


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@router.post("/semanal/enviar")
async def trigger_weekly_report(user: dict = Depends(require_role("admin", "financiero"))):
    """Envío manual del reporte ejecutivo."""
    return await send_weekly_report()


@router.get("/semanal/preview")
async def preview_weekly_report(user: dict = Depends(get_current_user)):
    """Devuelve sólo las estadísticas sin enviar email."""
    r = await build_weekly_report_html()
    return r["stats"]


@router.get("/semanal/config")
async def get_schedule_config(user: dict = Depends(get_current_user)):
    cfg  = await _get_schedule_config()
    job  = _scheduler.get_job("reporte_semanal") if _scheduler else None
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {
        **cfg,
        "day_label": DAY_NAMES_FULL[cfg["day_of_week"]],
        "next_run":  next_run,
        "timezone":  "America/Guayaquil",
    }


@router.put("/semanal/config")
async def update_schedule_config(body: ScheduleConfig, user: dict = Depends(require_role("admin"))):
    if not (0 <= body.day_of_week <= 6):
        raise HTTPException(400, "day_of_week debe ser 0-6")
    if not (0 <= body.hour <= 23):
        raise HTTPException(400, "hour debe ser 0-23")
    if not (0 <= body.minute <= 59):
        raise HTTPException(400, "minute debe ser 0-59")

    db      = get_db()
    new_cfg = {"day_of_week": body.day_of_week, "hour": body.hour, "minute": body.minute}
    await db.settings.update_one(
        {"key": "weekly_report"},
        {"$set": {**new_cfg, "key": "weekly_report", "updated_at": iso(now_utc())}},
        upsert=True,
    )
    _reschedule(new_cfg)

    job = _scheduler.get_job("reporte_semanal") if _scheduler else None
    return {
        **new_cfg,
        "day_label": DAY_NAMES_FULL[body.day_of_week],
        "next_run":  job.next_run_time.isoformat() if job and job.next_run_time else None,
        "timezone":  "America/Guayaquil",
    }
