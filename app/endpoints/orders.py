import asyncio
import os
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.order import Order

router = APIRouter()


class OrderItem(BaseModel):
    product_id: int
    variant_id: Optional[str] = None
    quantity: int = Field(default=1, ge=1)

    # опциональные поля для удобства в Telegram и истории
    product_name: Optional[str] = None
    price: Optional[float] = None
    size: Optional[str] = None
    color: Optional[str] = None
    image_url: Optional[str] = None
    vendor_code: Optional[str] = None


class OrderCreate(BaseModel):
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    customer_telegram_id: Optional[int] = None

    delivery_city: Optional[str] = None
    delivery_warehouse: Optional[str] = None
    payment_method: Optional[str] = "cash_on_delivery"

    items: List[OrderItem]
    notes: Optional[str] = None


def _item_to_dict(item: OrderItem) -> dict:
    if hasattr(item, "model_dump"):
        return item.model_dump(exclude_none=True)
    return item.dict(exclude_none=True)


def _build_order_total(items: List[OrderItem]) -> float:
    total = 0.0
    for item in items:
        if item.price is not None:
            total += float(item.price) * int(item.quantity)
    return total


def _send_telegram_notification(order: Order) -> None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("ADMIN_CHAT_ID")

    if not bot_token or not chat_id:
        return

    items_lines = []
    for item in order.items or []:
        name = item.get("product_name") or f"Товар #{item.get('product_id')}"
        qty = item.get("quantity", 1)
        price = item.get("price")
        variant = item.get("variant_id")
        size = item.get("size")
        color = item.get("color")
        vendor_code = item.get("vendor_code")

        details = []
        if vendor_code:
            details.append(f"арт: {vendor_code}")
        if size:
            details.append(f"розмір: {size}")
        if color:
            details.append(f"колір: {color}")

        suffix = f" ({', '.join(details)})" if details else ""
        if price is not None:
            items_lines.append(f"• {name}{suffix} ×{qty} — {float(price):.0f}₴")
        else:
            items_lines.append(f"• {name}{suffix} ×{qty}")

    items_text = "\n".join(items_lines) if items_lines else "—"

    text = (
        f"🛒 НОВЕ ЗАМОВЛЕННЯ #{order.id}\n"
        f"👤 {order.customer_name}\n"
        f"📞 {order.customer_phone}\n"
        f"✉️ {order.customer_email or '—'}\n"
        f"🚚 Нова Пошта: {order.delivery_city or '—'}, {order.delivery_warehouse or '—'}\n"
        f"💳 Оплата: накладений платіж\n\n"
        f"📦 Товари:\n{items_text}\n\n"
        f"💰 Разом: {order.total_price:.0f}₴"
    )

    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception:
        # Не роняем создание заказа, если Telegram недоступен.
        pass


@router.post("/")
async def create_order(order_data: OrderCreate, db: AsyncSession = Depends(get_db)):
    total = _build_order_total(order_data.items)

    order = Order(
        customer_name=order_data.customer_name,
        customer_phone=order_data.customer_phone,
        customer_email=order_data.customer_email,
        customer_telegram_id=order_data.customer_telegram_id,
        delivery_city=order_data.delivery_city,
        delivery_warehouse=order_data.delivery_warehouse,
        items=[_item_to_dict(item) for item in order_data.items],
        total_price=total,
        notes=order_data.notes,
        status="new",
    )

    db.add(order)
    await db.commit()
    await db.refresh(order)

    await asyncio.to_thread(_send_telegram_notification, order)

    return {
        "order_id": order.id,
        "id": order.id,
        "status": order.status,
    }


@router.get("/")
async def get_orders(
    db: AsyncSession = Depends(get_db),
    telegram_id: int | None = Query(default=None),
):
    stmt = select(Order)
    if telegram_id is not None:
        stmt = stmt.where(Order.customer_telegram_id == telegram_id)

    result = await db.execute(stmt.order_by(Order.created_at.desc()).limit(50))
    return result.scalars().all()
