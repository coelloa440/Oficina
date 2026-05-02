"""Router de autenticación: login, register, logout, me."""
from fastapi import APIRouter, Response, Depends

from core import (
    get_current_user, hash_password, verify_password,
    create_access_token, new_id, iso, now_utc,
)
from database import get_db
from models import UserCreate, LoginIn
from fastapi import HTTPException

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(body: UserCreate, response: Response):
    db = get_db()
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email ya registrado")
    user = {
        "id": new_id(), "email": email,
        "password_hash": hash_password(body.password),
        "name": body.name, "role": body.role,
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(user)
    token = create_access_token(user["id"], email, body.role)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=43200,
        path="/"
    )
    return {"id": user["id"], "email": email, "name": body.name, "role": body.role}


@router.post("/login")
async def login(body: LoginIn, response: Response):
    db = get_db()
    email = body.email.lower()
    user  = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_access_token(user["id"], email, user["role"])
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=43200,
        path="/"
    )
    return {"id": user["id"], "email": email, "name": user["name"], "role": user["role"]}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=True,
        samesite="none"
    )
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user
