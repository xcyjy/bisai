"""认证接口：注册 / 登录 / 当前用户。

Phase 1 用邮箱 + 密码（无需短信服务，本地即可测）。
手机号验证码 / 微信扫码见文档 05 第三节，后续接入。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from ..core.config import settings
from ..core.deps import get_current_user
from ..core.security import create_access_token, hash_password, verify_password
from ..db.models import User
from ..db.session import get_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    nickname: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def _user_public(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "nickname": u.nickname,
        "plan": u.plan,
        "credits": u.credits,
        "plan_expires_at": u.plan_expires_at.isoformat() if u.plan_expires_at else None,
    }


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, session: Session = Depends(get_session)):
    if len(req.password) < 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "密码至少 6 位")
    exists = session.exec(select(User).where(User.email == req.email)).first()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        nickname=req.nickname or req.email.split("@")[0],
        credits=settings.free_signup_credits,  # 注册赠送积分
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id), user=_user_public(user))


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == req.email)).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    return TokenResponse(access_token=create_access_token(user.id), user=_user_public(user))


@router.get("/me")
def me(current: User = Depends(get_current_user)):
    return _user_public(current)
