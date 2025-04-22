from aiogram import Bot
from dotenv import load_dotenv
import os
import asyncio
from contextlib import asynccontextmanager

# Load environment variables
load_dotenv()

def get_bot():
    return Bot(token=os.getenv("BOT_TOKEN"))

@asynccontextmanager
async def get_bot_session():
    try:
        yield get_bot()
    finally:
        await get_bot().session.close() 