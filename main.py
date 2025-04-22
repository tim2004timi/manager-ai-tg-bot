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

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = get_bot()
dp = Dispatcher()

# API endpoint for sending questions
API_URL = os.getenv("API_URL", "http://your-api-endpoint.com/chat")

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
                    "uuid": str(message.chat.id)
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    await message.answer(data["body"]["answer"])
                else:
                    await message.answer("Извините, произошла ошибка при обработке запроса")
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            await message.answer("Извините, произошла ошибка при обработке запроса")

def run_webhook():
    uvicorn.run(app, host="0.0.0.0", port=8000)

async def main():
    # Start webhook server in a separate thread
    webhook_thread = threading.Thread(target=run_webhook)
    webhook_thread.start()
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
