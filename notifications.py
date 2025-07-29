import os
import json
import logging
from typing import List, Dict, Set
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from crud import async_session, get_chat_by_uuid

# Загружаем список админов из переменной окружения
def get_admin_usernames() -> List[str]:
    """Получает список админов из переменной окружения"""
    admins_str = os.getenv("ADMIN_USERNAMES", "[]")
    try:
        return json.loads(admins_str)
    except json.JSONDecodeError:
        logging.error(f"Invalid ADMIN_USERNAMES format: {admins_str}")
        return []

# Файл для хранения настроек уведомлений админов
NOTIFICATIONS_FILE = "admin_notifications.json"

def load_notification_settings() -> Dict[str, bool]:
    """Загружает настройки уведомлений из файла"""
    try:
        if os.path.exists(NOTIFICATIONS_FILE):
            with open(NOTIFICATIONS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Error loading notification settings: {e}")
    return {}

def save_notification_settings(settings: Dict[str, bool]):
    """Сохраняет настройки уведомлений в файл"""
    try:
        with open(NOTIFICATIONS_FILE, 'w') as f:
            json.dump(settings, f)
    except Exception as e:
        logging.error(f"Error saving notification settings: {e}")

class NotificationManager:
    def __init__(self, bot):
        self.bot = bot
        self.admin_usernames = get_admin_usernames()
        self.notification_settings = load_notification_settings()
        
        # Инициализируем настройки для всех админов (по умолчанию включены)
        for username in self.admin_usernames:
            if username not in self.notification_settings:
                self.notification_settings[username] = True
        save_notification_settings(self.notification_settings)
    
    def get_notification_keyboard(self, username: str) -> InlineKeyboardMarkup:
        """Создает клавиатуру для управления уведомлениями"""
        is_enabled = self.notification_settings.get(username, True)
        
        if is_enabled:
            button_text = "🔕 Выкл уведомления"
            callback_data = f"notifications_off_{username}"
        else:
            button_text = "🔔 Вкл уведомления"
            callback_data = f"notifications_on_{username}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=button_text, callback_data=callback_data)]
        ])
        return keyboard
    
    async def send_waiting_notification(self, chat_id: int, chat_name: str, messager: str):
        """Отправляет уведомление о новом ожидающем чате"""
        message_text = (
            f"💬 Чат: {chat_name}\n"
            f"📱 Мессенджер: {messager.upper()}\n"
        )
        
        # Отправляем уведомления всем админам с включенными уведомлениями
        for username in self.admin_usernames:
            if self.notification_settings.get(username, True):
                try:
                    # Получаем chat_id админа по username
                    admin_chat_id = await self.get_admin_chat_id(username)
                    if admin_chat_id:
                        await self.bot.send_message(
                            chat_id=admin_chat_id,
                            text=message_text,
                            reply_markup=self.get_notification_keyboard(username)
                        )
                except Exception as e:
                    logging.error(f"Error sending notification to {username}: {e}")
    
    async def get_admin_chat_id(self, username: str) -> int:
        """Получает chat_id админа по username"""
        # Здесь нужно реализовать логику получения chat_id по username
        # Пока что будем использовать простой словарь
        # В реальном приложении это должно быть в базе данных
        admin_chat_ids = {}
        try:
            if os.path.exists("admin_chat_ids.json"):
                with open("admin_chat_ids.json", 'r') as f:
                    admin_chat_ids = json.load(f)
        except Exception as e:
            logging.error(f"Error loading admin chat IDs: {e}")
        
        return admin_chat_ids.get(username)
    
    async def save_admin_chat_id(self, username: str, chat_id: int):
        """Сохраняет chat_id админа"""
        admin_chat_ids = {}
        try:
            if os.path.exists("admin_chat_ids.json"):
                with open("admin_chat_ids.json", 'r') as f:
                    admin_chat_ids = json.load(f)
        except Exception as e:
            logging.error(f"Error loading admin chat IDs: {e}")
        
        admin_chat_ids[username] = chat_id
        
        try:
            with open("admin_chat_ids.json", 'w') as f:
                json.dump(admin_chat_ids, f)
        except Exception as e:
            logging.error(f"Error saving admin chat ID: {e}")
    
    async def toggle_notifications(self, username: str, chat_id: int):
        """Переключает настройки уведомлений для админа"""
        current_setting = self.notification_settings.get(username, True)
        self.notification_settings[username] = not current_setting
        save_notification_settings(self.notification_settings)
        
        # Сохраняем chat_id админа
        await self.save_admin_chat_id(username, chat_id)
        
        # Отправляем обновленную клавиатуру
        await self.bot.send_message(
            chat_id=chat_id,
            text=f"🔔 Уведомления {'включены' if self.notification_settings[username] else 'выключены'}",
            reply_markup=self.get_notification_keyboard(username)
        )

# Глобальный экземпляр менеджера уведомлений
notification_manager = None

def init_notification_manager(bot):
    """Инициализирует менеджер уведомлений"""
    global notification_manager
    notification_manager = NotificationManager(bot)
    return notification_manager

def get_notification_manager():
    """Возвращает экземпляр менеджера уведомлений"""
    return notification_manager 