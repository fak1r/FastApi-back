from fastapi import APIRouter, HTTPException, Depends
from schemas import TelegramOrderRequest
from datetime import datetime
from fastapi_limiter.depends import RateLimiter
from pytz import timezone
import httpx
import os

router = APIRouter(prefix="/order", tags=["Order"])

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ENABLE_RATE_LIMITER = os.getenv("ENABLE_RATE_LIMITER", "false").lower() == "true"

if ENABLE_RATE_LIMITER:
    from redis.asyncio import Redis

    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
    redis = Redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)

    async def get_next_order_number():
        return await redis.incr("global:order_counter")
else:
    async def get_next_order_number():
        return 0

dependencies = [Depends(RateLimiter(times=3, seconds=60))] if ENABLE_RATE_LIMITER else []

@router.post("/telegram", dependencies=dependencies)
async def send_telegram_order(data: TelegramOrderRequest):
    if not data.items:
        raise HTTPException(status_code=400, detail="Пустой заказ")

    order_number = await get_next_order_number()
    order_time = datetime.now(timezone("Europe/Moscow")).strftime("%d.%m.%Y %H:%M")
    source_text = "Купить сейчас" if data.source == "buy_now" else "Корзина"

    message = (
        f"📌 *Новый заказ №{order_number}* ({source_text})\n\n"
        f"📞 Клиент: `{data.phone}`\n"
        f"🕒 Время: {order_time}\n\n"
    )

    total = 0
    for item in data.items:
        item_total = item.quantity * item.price
        total += item_total
        message += (
            f"📦 *{item.name}*\n"
            f"💵 Кол-во: {item.quantity}, Цена: {item.price} ₽, Сумма: {item_total} ₽\n\n"
        )

    message += f"💰 *Итого:* {total} ₽"

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

    return {"success": True, "order_number": order_number}
