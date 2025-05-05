import asyncio
import logging
from aiogram import Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import aiohttp
from dotenv import load_dotenv
import os
import uvicorn
from webhook_server import app
import threading
from shared import get_bot
import websockets
import json

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = get_bot()
dp = Dispatcher()

# API endpoint for sending questions
API_URL = os.getenv("API_URL", "http://your-api-endpoint.com/chat")

# WebSocket client for frontend
ws_url = "ws://localhost:3002"
ws_connection = None

async def ws_connect():
    global ws_connection
    while True:
        try:
            ws_connection = await websockets.connect(ws_url)
            # Идентифицируемся как бот
            await ws_connection.send(json.dumps({"type": "bot"}))
            print("[WS] Connected to frontend WebSocket server")
            # Слушаем входящие сообщения от фронта (от менеджера)
            async for msg in ws_connection:
                try:
                    data = json.loads(msg)
                    # Ожидаем формат: { chat_id, message }
                    chat_id = int(data.get("chat_id"))
                    answer = data.get("message")
                    if chat_id and answer:
                        await bot.send_message(chat_id=chat_id, text=answer)
                except Exception as e:
                    print(f"[WS] Error handling incoming message: {e}")
        except Exception as e:
            print(f"[WS] Connection error: {e}, retrying in 5s...")
            await asyncio.sleep(5)

async def send_to_frontend_ws(payload):
    global ws_connection
    if ws_connection:
        try:
            await ws_connection.send(json.dumps(payload))
        except Exception as e:
            print(f"[WS] Send error: {e}")

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Добро пожаловать в Psihclothes!\n"
        "Можете задать любой вопрос"
    )

@dp.message()
async def handle_message(message: Message):
    if not message.text:
        await message.answer("Извините, но я понимаю только текстовые сообщения")
        return

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                API_URL,
                json={
                    "question": message.text,
                    "userId": str(message.chat.id)
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(data)
                    if data:
                        await message.answer(data["response"]["body"]["message"])
                        # Отправляем на фронтенд по WebSocket
                        await send_to_frontend_ws(data["response"]["body"])
                else:
                    await message.answer("Извините, произошла ошибка при обработке запроса")
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            await message.answer("Извините, произошла ошибка при обработке запроса")

def run_webhook():
    uvicorn.run(app, host="localhost", port=8000)

async def main():
    # Start webhook server in a separate thread
    webhook_thread = threading.Thread(target=run_webhook)
    webhook_thread.start()

    # Start WebSocket connection in background
    asyncio.create_task(ws_connect())

    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
