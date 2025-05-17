from fastapi import APIRouter, HTTPException
from schemas import TelegramOrderRequest
from datetime import datetime
import httpx
import os

router = APIRouter(prefix="/order", tags=["Order"])

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

@router.post("/telegram")
async def send_telegram_order(data: TelegramOrderRequest):
    if not data.items:
        raise HTTPException(status_code=400, detail="Пустой заказ")

    # Формируем сообщение
    order_time = datetime.now().strftime("%d.%m.%Y %H:%M")
    message = f"📌 *Новый заказ*\n\n📞 Клиент: `{data.phone}`\n🕒 Время: {order_time}\n\n"

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

    return {"success": True}
