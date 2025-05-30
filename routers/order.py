from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from schemas import TelegramOrderRequest
from datetime import datetime
from pytz import timezone
from database import get_db
from models import Order, OrderItem
import httpx
import os

from fastapi_limiter.depends import RateLimiter

router = APIRouter(prefix="/order", tags=["Order"])

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ENABLE_RATE_LIMITER = os.getenv("ENABLE_RATE_LIMITER", "false").lower() == "true"

dependencies = [Depends(RateLimiter(times=3, seconds=60))] if ENABLE_RATE_LIMITER else []

@router.post("/telegram", dependencies=dependencies)
async def send_telegram_order(
    data: TelegramOrderRequest,
    db: Session = Depends(get_db)
):
    if not data.items:
        raise HTTPException(status_code=400, detail="Пустой заказ")

    order_time = datetime.now(timezone("Europe/Moscow")).strftime("%d.%m.%Y %H:%M")
    source_text = "Купить сейчас" if data.source == "buy_now" else "Корзина"

    # Собираем JSON для базы и сообщение для Telegram
    items_json = []
    summary_string = ""
    total_amount = 0

    for item in data.items:
        item_total = item.quantity * item.price
        total_amount += item_total

        items_json.append({
            "full_name": item.full_name,
            "quantity": item.quantity,
            "price": item.price,
        })

        summary_string += (
            f"📦 *{item.full_name}*\n"
            f"💵 Кол-во: {item.quantity}, Цена: {item.price} ₽, Сумма: {item_total} ₽\n\n"
        )

    # Сохраняем заказ
    order = Order(
        customer_phone=data.phone,
        source=data.source,
        created_at=order_time,
        items_json=items_json,
        total_amount=total_amount
    )
    db.add(order)
    db.flush()

    for item in data.items:
        db.add(OrderItem(
            order_id=order.id,
            product_id=item.id,
            quantity=item.quantity,
        ))

    db.commit()

    # Отправка Telegram-сообщения
    message = (
        f"📌 *Новый заказ №{order.id}* ({source_text})\n\n"
        f"📞 Клиент: `{data.phone}`\n"
        f"🕒 Время: {order_time}\n\n"
        f"{summary_string}"
        f"💰 *Итого:* {total_amount} ₽"
    )

    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            send_url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            }
        )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Не удалось отправить заказ в Telegram")

    return {"success": True, "order_id": order.id}
