"""订单与支付：购买会员 / 积分包。

本地用 mock 支付（POST /pay 直接置为已支付并发放权益）。
云上接入微信/支付宝时，只需把权益发放逻辑移到真实异步回调里，业务不变。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..core.deps import get_current_user
from ..core.plans import catalog, get_sku
from ..db.models import Order, User
from ..db.session import get_session

router = APIRouter(prefix="/api", tags=["billing"])


class CreateOrderRequest(BaseModel):
    sku: str


@router.get("/plans")
def list_plans():
    """商品目录（套餐 + 积分包），供前端定价页展示。"""
    return catalog()


@router.post("/orders")
def create_order(
    req: CreateOrderRequest,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    sku = get_sku(req.sku)
    if sku is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "商品不存在")

    order = Order(
        user_id=current.id,
        sku=req.sku,
        title=sku["title"],
        amount_cny=sku["amount_cny"],
        grant_plan=sku.get("grant_plan", ""),
        grant_days=sku.get("grant_days", 0),
        grant_credits=sku.get("grant_credits", 0),
        status="pending",
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    # 真实环境这里返回支付二维码/跳转链接；本地返回 mock 支付入口
    return {
        "order_id": order.id,
        "title": order.title,
        "amount_cny": order.amount_cny,
        "pay_url": f"/api/orders/{order.id}/pay",   # mock：前端直接 POST 这个即可
        "status": order.status,
    }


@router.post("/orders/{order_id}/pay")
def mock_pay(
    order_id: int,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """模拟支付成功 -> 发放权益。真实环境替换为支付平台异步回调。"""
    order = session.get(Order, order_id)
    if order is None or order.user_id != current.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "订单不存在")
    if order.status == "paid":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "订单已支付")

    # 发放权益
    if order.grant_credits:
        current.credits += order.grant_credits
    if order.grant_plan:
        current.plan = order.grant_plan
        base = current.plan_expires_at
        if base is not None and base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)  # SQLite 读回无时区，补 UTC
        now = datetime.now(timezone.utc)
        # 已是会员则在原到期时间上续期，否则从现在起算
        start = base if (base and base > now) else now
        current.plan_expires_at = start + timedelta(days=order.grant_days)

    order.status = "paid"
    order.paid_at = datetime.now(timezone.utc)
    session.add(order)
    session.add(current)
    session.commit()
    session.refresh(current)
    return {
        "ok": True,
        "credits": current.credits,
        "plan": current.plan,
        "plan_expires_at": current.plan_expires_at.isoformat() if current.plan_expires_at else None,
    }


@router.get("/orders")
def list_orders(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(Order).where(Order.user_id == current.id).order_by(Order.id.desc())
    ).all()
    return [
        {
            "id": o.id, "title": o.title, "amount_cny": o.amount_cny,
            "status": o.status, "created_at": o.created_at.isoformat(),
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        }
        for o in rows
    ]
