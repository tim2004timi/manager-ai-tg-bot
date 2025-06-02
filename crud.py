import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func, select
from sqlalchemy.exc import SQLAlchemyError

# Load environment variables
load_dotenv()

# Database configuration
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy engine and session
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

# Models
class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, nullable=False)
    ai = Column(Boolean, default=False)
    waiting = Column(Boolean, default=False)
    messages = relationship("Message", back_populates="chat")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    message = Column(String, nullable=False)
    message_type = Column(String, nullable=False)
    ai = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    chat = relationship("Chat", back_populates="messages")

# CRUD operations
async def get_chats(db: AsyncSession):
    result = await db.execute(select(Chat).order_by(Chat.id.desc()))
    return result.scalars().all()

async def get_chat(db: AsyncSession, chat_id: int):
    result = await db.execute(select(Chat).filter(Chat.id == chat_id))
    return result.scalar_one_or_none()

async def get_messages(db: AsyncSession, chat_id: int):
    result = await db.execute(
        select(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
    )
    return result.scalars().all()

async def create_chat(db: AsyncSession, uuid: str, ai: bool = False):
    new_chat = Chat(uuid=uuid, ai=ai)
    db.add(new_chat)
    try:
        await db.commit()
        await db.refresh(new_chat)
        return new_chat
    except SQLAlchemyError:
        await db.rollback()
        raise

async def create_message(db: AsyncSession, chat_id: int, message: str, message_type: str, ai: bool = False):
    new_message = Message(chat_id=chat_id, message=message, message_type=message_type, ai=ai)
    db.add(new_message)
    try:
        await db.commit()
        await db.refresh(new_message)
        return new_message
    except SQLAlchemyError:
        await db.rollback()
        raise

async def update_chat_waiting(db: AsyncSession, chat_id: int, waiting: bool):
    chat = await get_chat(db, chat_id)
    if chat:
        chat.waiting = waiting
        await db.commit()
        await db.refresh(chat)
    return chat

async def update_chat_ai(db: AsyncSession, chat_id: int, ai: bool):
    chat = await get_chat(db, chat_id)
    if chat:
        chat.ai = ai
        await db.commit()
        await db.refresh(chat)
    return chat

async def get_stats(db: AsyncSession):
    total = await db.scalar(select(func.count(Chat.id)))
    pending = await db.scalar(select(func.count(Chat.id)).filter(Chat.waiting == True))
    ai_count = await db.scalar(select(func.count(Chat.id)).filter(Chat.ai == True))
    return {"total": total, "pending": pending, "ai": ai_count} 