from fastapi import APIRouter, Depends, HTTPException
from core import get_current_user
from database import get_db

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("")
async def listar_auditoria(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="No autorizado")

    db = get_db()

    logs = await (
        db.auditoria
        .find({}, {"_id": 0})
        .sort("fecha", -1)
        .to_list(300)
    )

    return logs