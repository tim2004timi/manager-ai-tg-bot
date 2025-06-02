import asyncio
import logging
from aiogram import Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import aiohttp
from dotenv import load_dotenv
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from crud import async_session, engine, Base, get_chats, get_chat, get_messages, create_chat, create_message, update_chat_waiting, update_chat_ai, get_stats
import requests
from pydantic import BaseModel
from shared import get_bot
import json
from contextlib import asynccontextmanager
from typing import List, Dict, Any

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = get_bot()
dp = Dispatcher()

# API endpoint for sending questions
API_URL = os.getenv("API_URL", "http://your-api-endpoint.com/chat")

# Create database tables
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    await init_db()
    # Start the bot polling in the background
    polling_task = asyncio.create_task(dp.start_polling(bot))
    yield
    # Cleanup
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
async def get_db():
    async with async_session() as session:
        yield session

# WebSocket connection managers
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logging.error(f"Error broadcasting message: {e}")

# Create separate managers for messages and updates
messages_manager = ConnectionManager()
updates_manager = ConnectionManager()

# WebSocket endpoints
@app.websocket("/ws/messages")
async def messages_websocket(websocket: WebSocket):
    await messages_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
                # If message is from frontend (manager), send it to the bot
                if "chat_id" in message_data and "message" in message_data:
                    try:
                        chat_id = int(message_data["chat_id"])
                        await bot.send_message(chat_id=chat_id, text=message_data["message"])
                    except (ValueError, TypeError) as e:
                        logging.error(f"Invalid chat_id format: {e}")
                # If message is from bot, broadcast it to all frontend clients
                else:
                    await messages_manager.broadcast(data)
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing message: {e}")
    except WebSocketDisconnect:
        messages_manager.disconnect(websocket)

@app.websocket("/ws/updates")
async def updates_websocket(websocket: WebSocket):
    await updates_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                update_data = json.loads(data)
                # Broadcast the update to all connected clients
                await updates_manager.broadcast(data)
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing update: {e}")
    except WebSocketDisconnect:
        updates_manager.disconnect(websocket)

# Endpoints
@app.get("/api/chats")
async def read_chats(db: AsyncSession = Depends(get_db)):
    return await get_chats(db)

@app.get("/api/chats/{chat_id}")
async def read_chat(chat_id: int, db: AsyncSession = Depends(get_db)):
    chat = await get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat

@app.get("/api/chats/{chat_id}/messages")
async def read_messages(chat_id: int, db: AsyncSession = Depends(get_db)):
    return await get_messages(db, chat_id)

# Schemas
class ChatCreate(BaseModel):
    uuid: str
    ai: bool = False

@app.post("/api/chats")
async def create_chat_endpoint(chat: ChatCreate, db: AsyncSession = Depends(get_db)):
    return await create_chat(db, chat.uuid, chat.ai)

class MessageCreate(BaseModel):
    chat_id: int
    message: str
    message_type: str
    ai: bool = False

@app.post("/api/messages")
async def create_message_endpoint(msg: MessageCreate, db: AsyncSession = Depends(get_db)):
    return await create_message(db, msg.chat_id, msg.message, msg.message_type, msg.ai)

class WaitingUpdate(BaseModel):
    waiting: bool

@app.put("/api/chats/{chat_id}/waiting")
async def update_waiting(chat_id: int, data: WaitingUpdate, db: AsyncSession = Depends(get_db)):
    chat = await update_chat_waiting(db, chat_id, data.waiting)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"success": True, "chat": chat}

class AIUpdate(BaseModel):
    ai: bool

@app.put("/api/chats/{chat_id}/ai")
async def update_ai(chat_id: int, data: AIUpdate, db: AsyncSession = Depends(get_db)):
    chat = await update_chat_ai(db, chat_id, data.ai)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat

@app.get("/api/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    return await get_stats(db)

@app.post("/api/webhook/messages")
async def proxy_webhook(payload: dict):
    webhook_url = os.getenv("WEBHOOK_URL")
    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, json=payload) as response:
            return await response.json(), response.status

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
                    if data:
                        if "answer" in data:
                            await message.answer(data["answer"]["message"])
                        # Отправляем на фронтенд по WebSocket
                        await messages_manager.broadcast(json.dumps(data))
                else:
                    await message.answer("Извините, произошла ошибка при обработке запроса")
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            await message.answer("Извините, произошла ошибка при обработке запроса")

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=3001)
