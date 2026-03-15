import os
import asyncio
import sqlite3
import json
import time
import random
import aiohttp
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import FloodWait, SessionPasswordNeeded, PhoneCodeInvalid, PhoneNumberInvalid, ApiIdInvalid
from pyrogram.errors import AccessTokenInvalid, UserIsBlocked, ChatAdminRequired, PeerIdInvalid
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Конфигурация бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_API_ID = 32480523  # Ваш API ID
BOT_API_HASH = "147839735c9fa4e83451209e9b55cfc5"  # Ваш API Hash
CRYPTO_BOT_API_KEY = "550080:AAtZpSCWuiY8cCQiKva4aHTU09b1teG2Rw6"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

MAX_ACCOUNTS_FREE = 3
MAX_ACCOUNTS_PAID = 10
MAX_CHATS_PER_MAILING = 100
CHATS_PER_PAGE = 10
DATABASE_PATH = "vest_soft.db"
PROMO_TEXT = "\n\n@VestSoftBot Лучший бот для рассылки"

# Режимы отправки
SEND_MODES = {
    "sequential": "По очереди (сначала все сообщения в 1 чат, потом в другой)",
    "random": "Рандом (случайный чат из выбранных)"
}

# Тарифы подписок
SUBSCRIPTION_PLANS = {
    "1day": {"name": "1 день", "price_rub": 3, "duration_days": 1},
    "7days": {"name": "7 дней", "price_rub": 10, "duration_days": 7},
    "forever": {"name": "Навсегда", "price_rub": 40, "duration_days": 99999}
}

# Курсы валют
EXCHANGE_RATES = {
    "USDT": 90,  # 1 USDT = 90 RUB
    "TON": 120   # 1 TON = 120 RUB
}

# Инициализация бота с API данными
app = Client(
    "vest_soft_bot",
    api_id=BOT_API_ID,
    api_hash=BOT_API_HASH,
    bot_token=BOT_TOKEN
)

# Клавиатуры
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📱 Менеджер аккаунтов")],
            [KeyboardButton("⚙️ Функции")],
            [KeyboardButton("👤 Профиль")]
        ],
        resize_keyboard=True
    )

def get_account_manager_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("➕ Добавить аккаунт")],
            [KeyboardButton("📋 Список аккаунтов")],
            [KeyboardButton("🔑 Выбрать активный аккаунт")],
            [KeyboardButton("❌ Удалить аккаунт")],
            [KeyboardButton("◀️ Назад в главное меню")]
        ],
        resize_keyboard=True
    )

def get_functions_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📨 Рассылка")],
            [KeyboardButton("🤖 Проверка спамблока")],
            [KeyboardButton("🔄 Автоответчик")],
            [KeyboardButton("◀️ Назад в главное меню")]
        ],
        resize_keyboard=True
    )

def get_autoreply_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📝 Установить автоответ")],
            [KeyboardButton("📋 Список автоответов")],
            [KeyboardButton("❌ Удалить автоответ")],
            [KeyboardButton("◀️ Назад в функции")]
        ],
        resize_keyboard=True
    )

def get_back_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("◀️ Назад")]],
        resize_keyboard=True
    )

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("❌ Отмена")]],
        resize_keyboard=True
    )

def get_chat_selection_keyboard(has_more: bool = False):
    keyboard = [
        [KeyboardButton("✅ Завершить выбор и продолжить")],
        [KeyboardButton("❌ Отмена")]
    ]
    
    if has_more:
        keyboard.insert(0, [KeyboardButton("📥 Загрузить ещё чаты")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_mailing_settings_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📝 Ввести сообщения")],
            [KeyboardButton("🔄 Режим: По очереди")],
            [KeyboardButton("⚡ Автоподписка: Выкл")],
            [KeyboardButton("✅ Запустить рассылку")],
            [KeyboardButton("❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_spamblock_accounts_keyboard(accounts: list):
    keyboard = []
    for acc in accounts:
        status = "✅" if acc.get('selected', False) else "⬜"
        keyboard.append([KeyboardButton(f"{status} {acc['name']} - {acc['phone']}")])
    
    keyboard.append([KeyboardButton("✅ Начать проверку")])
    keyboard.append([KeyboardButton("❌ Отмена")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_autoreply_chats_keyboard(chats: list, page: int = 0, total_pages: int = 1):
    keyboard = []
    start_idx = page * 5
    end_idx = min(start_idx + 5, len(chats))
    
    for i in range(start_idx, end_idx):
        chat = chats[i]
        status = "✅" if chat.get('selected', False) else "⬜"
        keyboard.append([KeyboardButton(f"{status} {chat['title']}")])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(KeyboardButton("⬅️ Назад"))
    if page < total_pages - 1:
        nav_buttons.append(KeyboardButton("➡️ Вперед"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([KeyboardButton("✅ Сохранить и продолжить")])
    keyboard.append([KeyboardButton("❌ Отмена")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_payment_methods_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 USDT", callback_data="pay_usdt")],
        [InlineKeyboardButton("💎 TON", callback_data="pay_ton")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_profile")]
    ])

# База данных
class Database:
    def __init__(self):
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(DATABASE_PATH)
    
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей бота
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    active_account_id INTEGER,
                    subscription_type TEXT DEFAULT 'free',
                    subscription_end TIMESTAMP,
                    mailing_status TEXT DEFAULT 'idle',
                    auto_subscribe_enabled BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица добавленных аккаунтов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    phone_number TEXT,
                    session_string TEXT,
                    account_name TEXT,
                    is_active BOOLEAN DEFAULT 0,
                    is_blocked BOOLEAN DEFAULT 0,
                    block_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица для временных данных (состояния)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS temp_data (
                    user_id INTEGER PRIMARY KEY,
                    data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для хранения чатов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    account_id INTEGER,
                    chat_id TEXT,
                    chat_title TEXT,
                    chat_type TEXT,
                    selected BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для хранения сообщений рассылки
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mailing_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для активных рассылок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS active_mailings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    account_id INTEGER,
                    messages TEXT,
                    chats TEXT,
                    send_mode TEXT,
                    message_count_per_chat INTEGER,
                    delay REAL,
                    auto_subscribe BOOLEAN DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    current_chat_index INTEGER DEFAULT 0,
                    current_message_index INTEGER DEFAULT 0,
                    sent_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для платежей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    invoice_id TEXT,
                    amount REAL,
                    currency TEXT,
                    plan_type TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для автоподписки
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS auto_subscribe (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    account_id INTEGER,
                    mailing_id INTEGER,
                    chat_id TEXT,
                    message_id INTEGER,
                    button_data TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для автоответчика
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS auto_replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    account_id INTEGER,
                    chat_id TEXT,
                    chat_title TEXT,
                    keywords TEXT,
                    reply_text TEXT,
                    reply_type TEXT DEFAULT 'exact',  -- 'exact', 'contains', 'regex'
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "user_id": row[0],
                    "active_account_id": row[1],
                    "subscription_type": row[2],
                    "subscription_end": row[3],
                    "mailing_status": row[4],
                    "auto_subscribe_enabled": bool(row[5]),
                    "created_at": row[6]
                }
            return None
    
    def create_user(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, subscription_type) VALUES (?, ?)",
                (user_id, "free")
            )
            conn.commit()
    
    def check_subscription(self, user_id: int) -> bool:
        """Проверяет, активна ли подписка у пользователя"""
        user = self.get_user(user_id)
        if not user:
            return False
        
        if user["subscription_type"] == "forever":
            return True
        
        if user["subscription_end"]:
            end_date = datetime.fromisoformat(user["subscription_end"])
            if datetime.now() < end_date:
                return True
        
        return False
    
    def get_max_accounts(self, user_id: int) -> int:
        """Возвращает максимальное количество аккаунтов для пользователя"""
        if self.check_subscription(user_id):
            return MAX_ACCOUNTS_PAID
        return MAX_ACCOUNTS_FREE
    
    def activate_subscription(self, user_id: int, plan_type: str):
        """Активирует подписку для пользователя"""
        plan = SUBSCRIPTION_PLANS[plan_type]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if plan_type == "forever":
                cursor.execute(
                    "UPDATE users SET subscription_type = 'forever', subscription_end = NULL WHERE user_id = ?",
                    (user_id,)
                )
            else:
                end_date = datetime.now() + timedelta(days=plan["duration_days"])
                cursor.execute(
                    "UPDATE users SET subscription_type = 'paid', subscription_end = ? WHERE user_id = ?",
                    (end_date.isoformat(), user_id)
                )
            
            conn.commit()
    
    def get_user_accounts(self, user_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM accounts WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            accounts = []
            for row in rows:
                accounts.append({
                    "id": row[0],
                    "user_id": row[1],
                    "phone_number": row[2],
                    "session_string": row[3],
                    "account_name": row[4],
                    "is_active": bool(row[5]),
                    "is_blocked": bool(row[6]),
                    "block_date": row[7],
                    "created_at": row[8]
                })
            return accounts
    
    def add_account(self, user_id: int, phone_number: str, session_string: str) -> int:
        accounts = self.get_user_accounts(user_id)
        account_name = f"Аккаунт {len(accounts) + 1}"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO accounts 
                   (user_id, phone_number, session_string, account_name) 
                   VALUES (?, ?, ?, ?)""",
                (user_id, phone_number, session_string, account_name)
            )
            account_id = cursor.lastrowid
            conn.commit()
            return account_id
    
    def delete_account(self, user_id: int, account_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM accounts WHERE id = ? AND user_id = ?",
                (account_id, user_id)
            )
            conn.commit()
    
    def set_active_account(self, user_id: int, account_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Сначала сбрасываем активный статус у всех аккаунтов пользователя
            cursor.execute(
                "UPDATE accounts SET is_active = 0 WHERE user_id = ?",
                (user_id,)
            )
            # Устанавливаем новый активный аккаунт
            cursor.execute(
                "UPDATE accounts SET is_active = 1 WHERE id = ? AND user_id = ?",
                (account_id, user_id)
            )
            # Обновляем в таблице users
            cursor.execute(
                "UPDATE users SET active_account_id = ? WHERE user_id = ?",
                (account_id, user_id)
            )
            conn.commit()
    
    def get_active_account(self, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM accounts WHERE user_id = ? AND is_active = 1",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "phone_number": row[2],
                    "session_string": row[3],
                    "account_name": row[4],
                    "is_active": bool(row[5]),
                    "is_blocked": bool(row[6]),
                    "block_date": row[7],
                    "created_at": row[8]
                }
            return None
    
    def save_temp_data(self, user_id: int, data: dict):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO temp_data (user_id, data) VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET data = ?, updated_at = CURRENT_TIMESTAMP""",
                (user_id, json.dumps(data), json.dumps(data))
            )
            conn.commit()
    
    def get_temp_data(self, user_id: int) -> dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM temp_data WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return {}
    
    def clear_temp_data(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM temp_data WHERE user_id = ?", (user_id,))
            conn.commit()
    
    def save_chats(self, user_id: int, account_id: int, chats: list):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Очищаем старые чаты
            cursor.execute(
                "DELETE FROM chats WHERE user_id = ? AND account_id = ?",
                (user_id, account_id)
            )
            # Добавляем новые чаты
            for chat in chats:
                cursor.execute(
                    """INSERT INTO chats (user_id, account_id, chat_id, chat_title, chat_type) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (user_id, account_id, str(chat['id']), chat['title'], chat.get('type', 'unknown'))
                )
            conn.commit()
    
    def get_chats(self, user_id: int, account_id: int, offset: int = 0, limit: int = CHATS_PER_PAGE) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM chats WHERE user_id = ? AND account_id = ? ORDER BY chat_title LIMIT ? OFFSET ?",
                (user_id, account_id, limit, offset)
            )
            rows = cursor.fetchall()
            chats = []
            for row in rows:
                chats.append({
                    "id": row[0],
                    "user_id": row[1],
                    "account_id": row[2],
                    "chat_id": row[3],
                    "chat_title": row[4],
                    "chat_type": row[5],
                    "selected": bool(row[6])
                })
            return chats
    
    def get_total_chats_count(self, user_id: int, account_id: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM chats WHERE user_id = ? AND account_id = ?",
                (user_id, account_id)
            )
            return cursor.fetchone()[0]
    
    def select_chat(self, user_id: int, account_id: int, chat_id: str, select: bool = True):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chats SET selected = ? WHERE user_id = ? AND account_id = ? AND chat_id = ?",
                (1 if select else 0, user_id, account_id, chat_id)
            )
            conn.commit()
    
    def clear_selected_chats(self, user_id: int, account_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chats SET selected = 0 WHERE user_id = ? AND account_id = ?",
                (user_id, account_id)
            )
            conn.commit()
    
    def get_selected_chats(self, user_id: int, account_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM chats WHERE user_id = ? AND account_id = ? AND selected = 1",
                (user_id, account_id)
            )
            rows = cursor.fetchall()
            chats = []
            for row in rows:
                chats.append({
                    "id": row[0],
                    "user_id": row[1],
                    "account_id": row[2],
                    "chat_id": row[3],
                    "chat_title": row[4],
                    "chat_type": row[5]
                })
            return chats
    
    def get_all_chats(self, user_id: int, account_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM chats WHERE user_id = ? AND account_id = ? ORDER BY chat_title",
                (user_id, account_id)
            )
            rows = cursor.fetchall()
            chats = []
            for row in rows:
                chats.append({
                    "id": row[0],
                    "user_id": row[1],
                    "account_id": row[2],
                    "chat_id": row[3],
                    "chat_title": row[4],
                    "chat_type": row[5],
                    "selected": bool(row[6])
                })
            return chats
    
    def save_mailing_messages(self, user_id: int, messages: List[str]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Очищаем старые сообщения
            cursor.execute("DELETE FROM mailing_messages WHERE user_id = ?", (user_id,))
            # Добавляем новые
            for msg in messages:
                cursor.execute(
                    "INSERT INTO mailing_messages (user_id, message_text) VALUES (?, ?)",
                    (user_id, msg)
                )
            conn.commit()
    
    def get_mailing_messages(self, user_id: int) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT message_text FROM mailing_messages WHERE user_id = ? ORDER BY id",
                (user_id,)
            )
            return [row[0] for row in cursor.fetchall()]
    
    def create_active_mailing(self, user_id: int, account_id: int, messages: List[str], 
                              chats: List[Dict], send_mode: str, message_count_per_chat: int, 
                              delay: float, auto_subscribe: bool) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO active_mailings 
                   (user_id, account_id, messages, chats, send_mode, message_count_per_chat, delay, auto_subscribe) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, account_id, json.dumps(messages), json.dumps(chats), 
                 send_mode, message_count_per_chat, delay, 1 if auto_subscribe else 0)
            )
            mailing_id = cursor.lastrowid
            
            # Обновляем статус пользователя
            cursor.execute(
                "UPDATE users SET mailing_status = 'active' WHERE user_id = ?",
                (user_id,)
            )
            
            conn.commit()
            return mailing_id
    
    def get_active_mailing(self, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM active_mailings WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "account_id": row[2],
                    "messages": json.loads(row[3]),
                    "chats": json.loads(row[4]),
                    "send_mode": row[5],
                    "message_count_per_chat": row[6],
                    "delay": row[7],
                    "auto_subscribe": bool(row[8]),
                    "status": row[9],
                    "current_chat_index": row[10],
                    "current_message_index": row[11],
                    "sent_count": row[12],
                    "created_at": row[13]
                }
            return None
    
    def update_mailing_progress(self, mailing_id: int, current_chat_index: int, 
                                current_message_index: int, sent_count: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE active_mailings 
                   SET current_chat_index = ?, current_message_index = ?, sent_count = ?
                   WHERE id = ?""",
                (current_chat_index, current_message_index, sent_count, mailing_id)
            )
            conn.commit()
    
    def complete_mailing(self, mailing_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE active_mailings SET status = 'completed' WHERE id = ?",
                (mailing_id,)
            )
            # Также обновляем статус пользователя
            cursor.execute(
                "UPDATE users SET mailing_status = 'idle' WHERE user_id = (SELECT user_id FROM active_mailings WHERE id = ?)",
                (mailing_id,)
            )
            conn.commit()
    
    def set_auto_subscribe(self, user_id: int, enabled: bool):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET auto_subscribe_enabled = ? WHERE user_id = ?",
                (1 if enabled else 0, user_id)
            )
            conn.commit()
    
    def get_auto_subscribe_status(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        return user.get("auto_subscribe_enabled", False) if user else False
    
    def add_auto_subscribe_task(self, user_id: int, account_id: int, mailing_id: int, 
                                chat_id: str, message_id: int, button_data: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO auto_subscribe 
                   (user_id, account_id, mailing_id, chat_id, message_id, button_data) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, account_id, mailing_id, chat_id, message_id, button_data)
            )
            conn.commit()
    
    def get_pending_auto_subscribe_tasks(self, mailing_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM auto_subscribe WHERE mailing_id = ? AND status = 'pending'",
                (mailing_id,)
            )
            rows = cursor.fetchall()
            tasks = []
            for row in rows:
                tasks.append({
                    "id": row[0],
                    "user_id": row[1],
                    "account_id": row[2],
                    "mailing_id": row[3],
                    "chat_id": row[4],
                    "message_id": row[5],
                    "button_data": json.loads(row[6]) if row[6] else None,
                    "status": row[7]
                })
            return tasks
    
    def complete_auto_subscribe_task(self, task_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE auto_subscribe SET status = 'completed' WHERE id = ?",
                (task_id,)
            )
            conn.commit()
    
    def create_payment(self, user_id: int, invoice_id: str, amount: float, currency: str, plan_type: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO payments (user_id, invoice_id, amount, currency, plan_type) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, invoice_id, amount, currency, plan_type)
            )
            conn.commit()
    
    def update_payment_status(self, invoice_id: str, status: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE payments SET status = ? WHERE invoice_id = ?",
                (status, invoice_id)
            )
            conn.commit()
    
    # Методы для автоответчика
    def add_auto_reply(self, user_id: int, account_id: int, chat_id: str, chat_title: str, 
                       keywords: List[str], reply_text: str, reply_type: str = 'exact'):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO auto_replies 
                   (user_id, account_id, chat_id, chat_title, keywords, reply_text, reply_type) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, account_id, chat_id, chat_title, json.dumps(keywords), reply_text, reply_type)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_auto_replies(self, user_id: int, account_id: Optional[int] = None) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if account_id:
                cursor.execute(
                    "SELECT * FROM auto_replies WHERE user_id = ? AND account_id = ? AND is_active = 1",
                    (user_id, account_id)
                )
            else:
                cursor.execute(
                    "SELECT * FROM auto_replies WHERE user_id = ? AND is_active = 1",
                    (user_id,)
                )
            rows = cursor.fetchall()
            replies = []
            for row in rows:
                replies.append({
                    "id": row[0],
                    "user_id": row[1],
                    "account_id": row[2],
                    "chat_id": row[3],
                    "chat_title": row[4],
                    "keywords": json.loads(row[5]),
                    "reply_text": row[6],
                    "reply_type": row[7],
                    "is_active": bool(row[8]),
                    "created_at": row[9]
                })
            return replies
    
    def get_auto_reply_for_chat(self, user_id: int, account_id: int, chat_id: str) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM auto_replies WHERE user_id = ? AND account_id = ? AND chat_id = ? AND is_active = 1",
                (user_id, account_id, chat_id)
            )
            rows = cursor.fetchall()
            replies = []
            for row in rows:
                replies.append({
                    "id": row[0],
                    "user_id": row[1],
                    "account_id": row[2],
                    "chat_id": row[3],
                    "chat_title": row[4],
                    "keywords": json.loads(row[5]),
                    "reply_text": row[6],
                    "reply_type": row[7],
                    "is_active": bool(row[8]),
                    "created_at": row[9]
                })
            return replies
    
    def delete_auto_reply(self, reply_id: int, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM auto_replies WHERE id = ? AND user_id = ?",
                (reply_id, user_id)
            )
            conn.commit()
    
    def toggle_auto_reply(self, reply_id: int, user_id: int, active: bool):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE auto_replies SET is_active = ? WHERE id = ? AND user_id = ?",
                (1 if active else 0, reply_id, user_id)
            )
            conn.commit()

# Инициализация базы данных
db = Database()

# Временные клиенты для аккаунтов пользователей
user_clients = {}

async def get_user_client(user_id: int, account: dict) -> Optional[Client]:
    """Получить или создать клиент для аккаунта пользователя"""
    client_key = f"{user_id}_{account['id']}"
    
    if client_key in user_clients:
        try:
            # Проверяем, работает ли клиент
            await user_clients[client_key].get_me()
            return user_clients[client_key]
        except:
            # Если не работает, удаляем и создаем новый
            try:
                await user_clients[client_key].stop()
            except:
                pass
            del user_clients[client_key]
    
    # Создаем новый клиент
    client = Client(
        f"user_{user_id}_{account['id']}",
        api_id=BOT_API_ID,
        api_hash=BOT_API_HASH,
        session_string=account['session_string'],
        in_memory=True
    )
    
    try:
        await client.start()
        user_clients[client_key] = client
        return client
    except Exception as e:
        print(f"Ошибка запуска клиента: {e}")
        return None

async def stop_user_client(user_id: int, account_id: int):
    """Остановить клиент аккаунта"""
    client_key = f"{user_id}_{account_id}"
    if client_key in user_clients:
        try:
            await user_clients[client_key].stop()
        except:
            pass
        finally:
            del user_clients[client_key]

async def create_crypto_invoice(amount: float, currency: str, user_id: int, plan_type: str) -> Optional[dict]:
    """Создание счета в Crypto Bot"""
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Конвертируем рубли в выбранную валюту
    if currency == "USDT":
        crypto_amount = round(amount / EXCHANGE_RATES["USDT"], 2)
        asset = "USDT"
    else:  # TON
        crypto_amount = round(amount / EXCHANGE_RATES["TON"], 2)
        asset = "TON"
    
    payload = {
        "asset": asset,
        "amount": str(crypto_amount),
        "description": f"Подписка VestSoft - {SUBSCRIPTION_PLANS[plan_type]['name']}",
        "payload": json.dumps({"user_id": user_id, "plan_type": plan_type})
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        return data["result"]
                return None
        except Exception as e:
            print(f"Ошибка создания счета: {e}")
            return None

async def check_invoice_status(invoice_id: str) -> Optional[str]:
    """Проверка статуса счета"""
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_API_KEY
    }
    
    params = {
        "invoice_ids": invoice_id
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok") and data.get("result", {}).get("items"):
                        return data["result"]["items"][0]["status"]
                return None
        except Exception as e:
            print(f"Ошибка проверки счета: {e}")
            return None

# Обработчики команд
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    db.create_user(user_id)
    
    await message.reply_text(
        "👋 Добро пожаловать в VEST SOFT Bot!\n\n"
        "Я помогу вам управлять несколькими Telegram аккаунтами "
        "и делать рассылки по чатам.\n\n"
        "Используйте кнопки меню для навигации.",
        reply_markup=get_main_keyboard()
    )

@app.on_message(filters.command("done"))
async def done_entering_messages(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'entering_messages':
        await message.reply_text("❌ Нечего завершать.")
        return
    
    messages = temp_data.get('temp_messages', [])
    
    if not messages:
        await message.reply_text("❌ Вы не ввели ни одного сообщения.")
        return
    
    # Сохраняем сообщения
    temp_data['step'] = 'mailing_settings'
    temp_data['messages'] = messages
    del temp_data['temp_messages']
    db.save_temp_data(user_id, temp_data)
    
    # Сохраняем в БД
    db.save_mailing_messages(user_id, messages)
    
    await message.reply_text(f"✅ Сохранено {len(messages)} сообщений.")
    await show_mailing_settings(client, message, user_id)

@app.on_message(filters.command("done_keywords"))
async def done_entering_keywords(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'entering_keywords':
        await message.reply_text("❌ Нечего завершать.")
        return
    
    keywords = temp_data.get('temp_keywords', [])
    
    if not keywords:
        await message.reply_text("❌ Вы не ввели ни одного ключевого слова.")
        return
    
    temp_data['keywords'] = keywords
    temp_data['step'] = 'entering_reply_text'
    del temp_data['temp_keywords']
    db.save_temp_data(user_id, temp_data)
    
    await message.reply_text(
        f"✅ Сохранено {len(keywords)} ключевых слов.\n\n"
        "✏️ Теперь введите текст для автоответа:",
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.text & filters.regex("^📱 Менеджер аккаунтов$"))
async def account_manager_menu(client: Client, message: Message):
    await message.reply_text(
        "📱 Менеджер аккаунтов\n\n"
        "Выберите действие:",
        reply_markup=get_account_manager_keyboard()
    )

@app.on_message(filters.text & filters.regex("^📋 Список аккаунтов$"))
async def list_accounts(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    max_accounts = db.get_max_accounts(user_id)
    
    if not accounts:
        await message.reply_text(
            "📋 У вас пока нет добавленных аккаунтов.",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    text = "📋 Список ваших аккаунтов:\n\n"
    for acc in accounts:
        status = "✅ АКТИВЕН" if acc['is_active'] else "❌ не активен"
        block_status = " (ЗАБЛОКИРОВАН)" if acc['is_blocked'] else ""
        text += f"• {acc['account_name']}: {acc['phone_number']} - {status}{block_status}\n"
    
    text += f"\nВсего аккаунтов: {len(accounts)}/{max_accounts}"
    
    await message.reply_text(
        text,
        reply_markup=get_account_manager_keyboard()
    )

@app.on_message(filters.text & filters.regex("^➕ Добавить аккаунт$"))
async def add_account_start(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    max_accounts = db.get_max_accounts(user_id)
    
    if len(accounts) >= max_accounts:
        await message.reply_text(
            f"❌ Вы достигли лимита в {max_accounts} аккаунтов.\n"
            f"Купите подписку, чтобы увеличить лимит до {MAX_ACCOUNTS_PAID} аккаунтов.",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    db.save_temp_data(user_id, {"step": "waiting_phone"})
    
    await message.reply_text(
        "📱 Для добавления аккаунта введите номер телефона\n"
        "в международном формате (например: +79001234567):",
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.text & filters.regex("^❌ Удалить аккаунт$"))
async def delete_account_menu(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await message.reply_text(
            "❌ У вас нет добавленных аккаунтов.",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    # Сохраняем список аккаунтов во временные данные
    db.save_temp_data(user_id, {"step": "deleting_account", "accounts": accounts})
    
    text = "❌ Выберите аккаунт для удаления:\n\n"
    for i, acc in enumerate(accounts, 1):
        text += f"{i}. {acc['account_name']} - {acc['phone_number']}\n"
    text += "\nОтправьте номер аккаунта (1, 2, 3...) или нажмите Отмена"
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.text & filters.regex("^🔑 Выбрать активный аккаунт$"))
async def select_active_account_menu(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await message.reply_text(
            "❌ У вас нет добавленных аккаунтов.",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    # Сохраняем список аккаунтов во временные данные
    db.save_temp_data(user_id, {"step": "selecting_account", "accounts": accounts})
    
    text = "🔑 Выберите активный аккаунт:\n\n"
    for i, acc in enumerate(accounts, 1):
        status = " (текущий)" if acc['is_active'] else ""
        text += f"{i}. {acc['account_name']} - {acc['phone_number']}{status}\n"
    text += "\nОтправьте номер аккаунта (1, 2, 3...) или нажмите Отмена"
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.text & filters.regex("^⚙️ Функции$"))
async def functions_menu(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ Сначала выберите активный аккаунт в Менеджере аккаунтов.\n"
            "Используйте кнопку '🔑 Выбрать активный аккаунт'",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    await message.reply_text(
        f"⚙️ Функции\n\n"
        f"Активный аккаунт: {active_account['account_name']} ({active_account['phone_number']})\n\n"
        f"Выберите функцию:",
        reply_markup=get_functions_keyboard()
    )

@app.on_message(filters.text & filters.regex("^🤖 Проверка спамблока$"))
async def spamblock_check_start(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if len(accounts) == 0:
        await message.reply_text(
            "❌ У вас нет добавленных аккаунтов.",
            reply_markup=get_functions_keyboard()
        )
        return
    
    # Сохраняем состояние
    temp_accounts = []
    for acc in accounts:
        temp_accounts.append({
            "id": acc["id"], 
            "name": acc["account_name"], 
            "phone": acc["phone_number"], 
            "selected": False
        })
    
    db.save_temp_data(user_id, {
        "step": "selecting_spamblock_accounts",
        "accounts": temp_accounts
    })
    
    await message.reply_text(
        "🤖 Проверка спамблока\n\n"
        "Выберите аккаунты для проверки (можно несколько):\n"
        "Нажимайте на кнопки с аккаунтами, чтобы выбрать/отменить выбор.\n"
        "Когда выберете нужные, нажмите '✅ Начать проверку'",
        reply_markup=get_spamblock_accounts_keyboard(temp_accounts)
    )

@app.on_message(filters.text & filters.regex("^🔄 Автоответчик$"))
async def autoreply_menu(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ Сначала выберите активный аккаунт.",
            reply_markup=get_functions_keyboard()
        )
        return
    
    await message.reply_text(
        "🔄 Меню автоответчика\n\n"
        "Здесь вы можете настроить автоматические ответы на сообщения в чатах.\n\n"
        "Выберите действие:",
        reply_markup=get_autoreply_keyboard()
    )

@app.on_message(filters.text & filters.regex("^📝 Установить автоответ$"))
async def setup_autoreply_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ Сначала выберите активный аккаунт.",
            reply_markup=get_functions_keyboard()
        )
        return
    
    # Получаем все чаты аккаунта
    chats = db.get_all_chats(user_id, active_account['id'])
    
    if not chats:
        await message.reply_text(
            "❌ Сначала загрузите чаты через функцию 'Рассылка'.",
            reply_markup=get_autoreply_keyboard()
        )
        return
    
    # Отмечаем все чаты как невыбранные
    for chat in chats:
        chat['selected'] = False
    
    db.save_temp_data(user_id, {
        "step": "selecting_autoreply_chats",
        "account_id": active_account['id'],
        "chats": chats,
        "page": 0
    })
    
    total_pages = (len(chats) + 4) // 5
    await show_autoreply_chats_page(client, message, user_id, 0, total_pages)

async def show_autoreply_chats_page(client: Client, message: Message, user_id: int, page: int, total_pages: int):
    temp_data = db.get_temp_data(user_id)
    chats = temp_data.get('chats', [])
    
    await message.reply_text(
        f"📋 Выберите чаты для автоответа (страница {page + 1}/{total_pages}):\n\n"
        "Нажимайте на кнопки с чатами, чтобы выбрать/отменить выбор.\n"
        "Когда закончите, нажмите '✅ Сохранить и продолжить'",
        reply_markup=get_autoreply_chats_keyboard(chats, page, total_pages)
    )

@app.on_message(filters.text & filters.regex("^📋 Список автоответов$"))
async def list_autoreplies(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ Сначала выберите активный аккаунт.",
            reply_markup=get_functions_keyboard()
        )
        return
    
    replies = db.get_auto_replies(user_id, active_account['id'])
    
    if not replies:
        await message.reply_text(
            "📋 У вас нет настроенных автоответов.",
            reply_markup=get_autoreply_keyboard()
        )
        return
    
    text = "📋 Список автоответов:\n\n"
    for i, reply in enumerate(replies, 1):
        keywords = ", ".join(reply['keywords'][:3])
        if len(reply['keywords']) > 3:
            keywords += f" и еще {len(reply['keywords']) - 3}"
        
        text += f"{i}. Чат: {reply['chat_title']}\n"
        text += f"   Ключевые слова: {keywords}\n"
        text += f"   Ответ: {reply['reply_text'][:50]}...\n"
        text += f"   ID: {reply['id']}\n\n"
    
    await message.reply_text(
        text,
        reply_markup=get_autoreply_keyboard()
    )

@app.on_message(filters.text & filters.regex("^❌ Удалить автоответ$"))
async def delete_autoreply_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ Сначала выберите активный аккаунт.",
            reply_markup=get_functions_keyboard()
        )
        return
    
    replies = db.get_auto_replies(user_id, active_account['id'])
    
    if not replies:
        await message.reply_text(
            "📋 У вас нет настроенных автоответов.",
            reply_markup=get_autoreply_keyboard()
        )
        return
    
    # Сохраняем список автоответов
    db.save_temp_data(user_id, {
        "step": "deleting_autoreply",
        "replies": replies
    })
    
    text = "❌ Выберите автоответ для удаления:\n\n"
    for i, reply in enumerate(replies, 1):
        text += f"{i}. Чат: {reply['chat_title']} - {reply['reply_text'][:30]}...\n"
    text += "\nОтправьте номер автоответа (1, 2, 3...) или нажмите Отмена"
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.text & filters.regex("^📨 Рассылка$"))
async def mailing_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ Сначала выберите активный аккаунт.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Проверяем, не запущена ли уже рассылка
    active_mailing = db.get_active_mailing(user_id)
    if active_mailing:
        await message.reply_text(
            "⚠️ У вас уже есть активная рассылка. Сначала завершите её.",
            reply_markup=get_main_keyboard()
        )
        return
    
    status_msg = await message.reply_text(
        "🔄 Загружаю список ваших чатов... Это может занять некоторое время.",
        reply_markup=get_back_keyboard()
    )
    
    # Получаем клиент для аккаунта
    user_client = await get_user_client(user_id, active_account)
    if not user_client:
        await status_msg.edit_text(
            "❌ Не удалось подключиться к аккаунту. Попробуйте добавить его заново.",
            reply_markup=get_functions_keyboard()
        )
        return
    
    try:
        # Получаем информацию о пользователе
        me = await user_client.get_me()
        
        # Загружаем все диалоги (группы и каналы)
        all_chats = []
        async for dialog in user_client.get_dialogs():
            # Проверяем тип чата
            chat_type = dialog.chat.type
            if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                # Получаем правильный ID для отправки сообщений
                chat_id = dialog.chat.id
                
                # Для каналов и супергрупп ID может быть отрицательным
                # Но при отправке сообщений нужно использовать именно этот ID
                
                chat_info = {
                    'id': chat_id,
                    'title': dialog.chat.title or "Без названия",
                    'type': str(chat_type).split('.')[-1]  # GROUP, SUPERGROUP, CHANNEL
                }
                all_chats.append(chat_info)
                
                print(f"Найден чат: {chat_info['title']} (ID: {chat_info['id']}, Тип: {chat_info['type']})")
        
        if not all_chats:
            await status_msg.edit_text(
                "❌ У вас нет групп или каналов для рассылки.",
                reply_markup=get_functions_keyboard()
            )
            return
        
        # Сохраняем чаты в БД (старые удалятся автоматически)
        db.save_chats(user_id, active_account['id'], all_chats)
        db.clear_selected_chats(user_id, active_account['id'])
        
        await status_msg.edit_text(
            f"✅ Загружено {len(all_chats)} чатов.",
            reply_markup=get_back_keyboard()
        )
        
        # Сохраняем состояние
        db.save_temp_data(user_id, {
            "step": "selecting_chats",
            "account_id": active_account['id'],
            "offset": 0,
            "selected_chats": []
        })
        
        # Показываем первые чаты
        await show_chats_page(client, message, user_id, active_account['id'], 0)
        
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Ошибка при загрузке чатов: {str(e)}",
            reply_markup=get_functions_keyboard()
        )

async def show_chats_page(client: Client, message: Message, user_id: int, account_id: int, offset: int):
    """Показать страницу с чатами для выбора"""
    chats = db.get_chats(user_id, account_id, offset, CHATS_PER_PAGE)
    total_chats = db.get_total_chats_count(user_id, account_id)
    selected = db.get_selected_chats(user_id, account_id)
    
    if not chats:
        if offset == 0:
            await message.reply_text(
                "❌ Чаты не найдены.",
                reply_markup=get_functions_keyboard()
            )
        else:
            # Если чаты закончились, показываем выбранные
            await show_selected_chats_summary(client, message, user_id, account_id)
        return
    
    # Формируем сообщение со списком чатов
    text = f"📢 Выберите чаты для рассылки (макс. {MAX_CHATS_PER_MAILING})\n\n"
    text += f"Страница {offset//CHATS_PER_PAGE + 1}/{(total_chats-1)//CHATS_PER_PAGE + 1}\n"
    text += f"Всего чатов: {total_chats}\n"
    text += f"Выбрано: {len(selected)}/{MAX_CHATS_PER_MAILING}\n\n"
    
    for i, chat in enumerate(chats, start=offset+1):
        status = "✅" if chat['selected'] else "⬜"
        text += f"{status} {i}. {chat['chat_title']}\n"
        text += f"   Тип: {chat['chat_type']}\n\n"
    
    text += "\nЧтобы выбрать чат, отправьте его номер (например: 1, 2, 3)\n"
    text += "Можно выбирать несколько чатов, отправляя номера по одному."
    
    # Сохраняем текущий offset в temp_data
    temp_data = db.get_temp_data(user_id)
    temp_data['offset'] = offset
    db.save_temp_data(user_id, temp_data)
    
    # Определяем, есть ли еще чаты
    has_more = (offset + CHATS_PER_PAGE) < total_chats
    
    await message.reply_text(
        text,
        reply_markup=get_chat_selection_keyboard(has_more)
    )

async def show_selected_chats_summary(client: Client, message: Message, user_id: int, account_id: int):
    """Показать сводку выбранных чатов и перейти к настройкам рассылки"""
    selected = db.get_selected_chats(user_id, account_id)
    
    if not selected:
        await message.reply_text(
            "❌ Вы не выбрали ни одного чата.",
            reply_markup=get_functions_keyboard()
        )
        return
    
    if len(selected) > MAX_CHATS_PER_MAILING:
        await message.reply_text(
            f"❌ Выбрано слишком много чатов ({len(selected)}). Максимум: {MAX_CHATS_PER_MAILING}",
            reply_markup=get_functions_keyboard()
        )
        return
    
    # Сохраняем состояние для настройки рассылки
    db.save_temp_data(user_id, {
        "step": "mailing_settings",
        "account_id": account_id,
        "chats": selected,
        "messages": [],
        "send_mode": "sequential",
        "message_count": 1,
        "delay": 1.0,
        "auto_subscribe": False
    })
    
    await show_mailing_settings(client, message, user_id)

async def show_mailing_settings(client: Client, message: Message, user_id: int):
    """Показать настройки рассылки"""
    temp_data = db.get_temp_data(user_id)
    messages = temp_data.get('messages', [])
    send_mode = temp_data.get('send_mode', 'sequential')
    auto_subscribe = temp_data.get('auto_subscribe', False)
    
    text = "⚙️ Настройки рассылки:\n\n"
    text += f"📝 Сообщений: {len(messages)} шт.\n"
    if messages:
        text += f"   Первое: {messages[0][:50]}...\n"
    text += f"🔄 Режим: {SEND_MODES[send_mode]}\n"
    text += f"⚡ Автоподписка: {'Вкл' if auto_subscribe else 'Выкл'}\n\n"
    text += "Используйте кнопки ниже для настройки:"
    
    await message.reply_text(
        text,
        reply_markup=get_mailing_settings_keyboard()
    )

@app.on_message(filters.text & filters.regex("^📝 Ввести сообщения$"))
async def enter_messages(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'mailing_settings':
        await message.reply_text("❌ Ошибка. Начните заново.")
        return
    
    temp_data['step'] = 'entering_messages'
    temp_data['temp_messages'] = []
    db.save_temp_data(user_id, temp_data)
    
    await message.reply_text(
        "📝 Введите сообщения для рассылки (по одному в сообщении).\n"
        "Когда закончите, отправьте /done\n\n"
        f"Максимум сообщений: {MAX_CHATS_PER_MAILING}",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("/done")], [KeyboardButton("❌ Отмена")]],
            resize_keyboard=True
        )
    )

@app.on_message(filters.text & filters.regex("^🔄 Режим: По очереди$|^🔄 Режим: Рандом$"))
async def toggle_send_mode(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'mailing_settings':
        return
    
    current_mode = temp_data.get('send_mode', 'sequential')
    new_mode = 'random' if current_mode == 'sequential' else 'sequential'
    temp_data['send_mode'] = new_mode
    db.save_temp_data(user_id, temp_data)
    
    # Обновляем настройки
    await show_mailing_settings(client, message, user_id)

@app.on_message(filters.text & filters.regex("^⚡ Автоподписка: Выкл$|^⚡ Автоподписка: Вкл$"))
async def toggle_auto_subscribe(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'mailing_settings':
        return
    
    current = temp_data.get('auto_subscribe', False)
    temp_data['auto_subscribe'] = not current
    db.save_temp_data(user_id, temp_data)
    
    # Обновляем настройки
    await show_mailing_settings(client, message, user_id)

@app.on_message(filters.text & filters.regex("^✅ Запустить рассылку$"))
async def start_mailing_from_settings(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'mailing_settings':
        await message.reply_text("❌ Ошибка. Начните заново.")
        return
    
    messages = temp_data.get('messages', [])
    if not messages:
        await message.reply_text("❌ Сначала введите сообщения для рассылки.")
        return
    
    chats = temp_data.get('chats', [])
    if not chats:
        await message.reply_text("❌ Ошибка с выбором чатов.")
        return
    
    account_id = temp_data.get('account_id')
    if not account_id:
        await message.reply_text("❌ Ошибка с аккаунтом.")
        return
    
    active_account = db.get_active_account(user_id)
    if not active_account or active_account['id'] != account_id:
        await message.reply_text("❌ Активный аккаунт изменился.")
        return
    
    # Запрашиваем количество сообщений на чат
    temp_data['step'] = 'waiting_message_count'
    db.save_temp_data(user_id, temp_data)
    
    await message.reply_text(
        "✏️ Сколько сообщений отправить в каждый чат?\n"
        f"(максимум: {MAX_CHATS_PER_MAILING})",
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.text & filters.regex("^📥 Загрузить ещё чаты$"))
async def load_more_chats(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    account_id = temp_data.get('account_id')
    current_offset = temp_data.get('offset', 0)
    
    if not account_id:
        await message.reply_text("❌ Ошибка. Начните заново.")
        return
    
    # Показываем следующую страницу
    await show_chats_page(client, message, user_id, account_id, current_offset + CHATS_PER_PAGE)

@app.on_message(filters.text & filters.regex("^✅ Завершить выбор и продолжить$"))
async def finish_chat_selection(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    account_id = temp_data.get('account_id')
    
    if not account_id:
        await message.reply_text("❌ Ошибка. Начните заново.")
        return
    
    await show_selected_chats_summary(client, message, user_id, account_id)

@app.on_message(filters.text & filters.regex("^👤 Профиль$"))
async def profile_menu(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    active_account = db.get_active_account(user_id)
    has_subscription = db.check_subscription(user_id)
    user_data = db.get_user(user_id)
    max_accounts = db.get_max_accounts(user_id)
    
    text = "👤 Ваш профиль\n\n"
    text += f"Telegram ID: `{user_id}`\n"
    text += f"Аккаунтов добавлено: {len(accounts)}/{max_accounts}\n\n"
    
    # Информация о подписке
    text += "💎 Статус подписки: "
    if has_subscription:
        if user_data["subscription_type"] == "forever":
            text += "Навсегда\n"
        elif user_data["subscription_end"]:
            end_date = datetime.fromisoformat(user_data["subscription_end"])
            days_left = (end_date - datetime.now()).days
            text += f"Активна (осталось {days_left} дн.)\n"
        else:
            text += "Активна\n"
    else:
        text += "Бесплатная\n"
        text += f"⚡ Лимит аккаунтов: {MAX_ACCOUNTS_FREE}\n"
        text += f"⚡ Купите подписку для увеличения лимита до {MAX_ACCOUNTS_PAID}\n\n"
    
    if active_account:
        text += f"\n✅ Активный аккаунт:\n"
        text += f"• {active_account['account_name']}\n"
        text += f"• {active_account['phone_number']}"
    else:
        text += "\n❌ Активный аккаунт не выбран"
    
    # Добавляем кнопки для покупки подписки
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Купить подписку", callback_data="buy_subscription")],
        [InlineKeyboardButton("🔄 Проверить оплату", callback_data="check_payment")]
    ])
    
    await message.reply_text(
        text,
        reply_markup=keyboard
    )

@app.on_message(filters.text & filters.regex("^◀️ Назад в главное меню$|^◀️ Назад$"))
async def back_to_main(client: Client, message: Message):
    user_id = message.from_user.id
    db.clear_temp_data(user_id)
    await message.reply_text(
        "Главное меню:",
        reply_markup=get_main_keyboard()
    )

@app.on_message(filters.text & filters.regex("^◀️ Назад в функции$"))
async def back_to_functions(client: Client, message: Message):
    user_id = message.from_user.id
    db.clear_temp_data(user_id)
    await message.reply_text(
        "⚙️ Функции:",
        reply_markup=get_functions_keyboard()
    )

@app.on_message(filters.text & filters.regex("^❌ Отмена$"))
async def cancel_action(client: Client, message: Message):
    user_id = message.from_user.id
    db.clear_temp_data(user_id)
    await message.reply_text(
        "Действие отменено.",
        reply_markup=get_main_keyboard()
    )

# Обработчики для автоответчика
@app.on_message(filters.text & filters.regex("^[⬜✅] .*$") & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'selecting_autoreply_chats'))
async def handle_autoreply_chat_selection(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    text = message.text
    # Убираем эмодзи в начале
    if text.startswith('✅ ') or text.startswith('⬜ '):
        chat_title = text[2:]
    else:
        chat_title = text
    
    # Ищем чат
    for chat in temp_data['chats']:
        if chat['chat_title'] == chat_title:
            chat['selected'] = not chat.get('selected', False)
            db.save_temp_data(user_id, temp_data)
            
            # Обновляем страницу
            page = temp_data.get('page', 0)
            total_pages = (len(temp_data['chats']) + 4) // 5
            await message.reply_text(
                f"{'✅' if chat['selected'] else '⬜'} Чат '{chat_title}' {'выбран' if chat['selected'] else 'отменен'}",
                reply_markup=get_autoreply_chats_keyboard(temp_data['chats'], page, total_pages)
            )
            return

@app.on_message(filters.text & filters.regex("^⬅️ Назад$") & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'selecting_autoreply_chats'))
async def autoreply_prev_page(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    current_page = temp_data.get('page', 0)
    if current_page > 0:
        temp_data['page'] = current_page - 1
        db.save_temp_data(user_id, temp_data)
        
        total_pages = (len(temp_data['chats']) + 4) // 5
        await show_autoreply_chats_page(client, message, user_id, current_page - 1, total_pages)

@app.on_message(filters.text & filters.regex("^➡️ Вперед$") & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'selecting_autoreply_chats'))
async def autoreply_next_page(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    current_page = temp_data.get('page', 0)
    total_pages = (len(temp_data['chats']) + 4) // 5
    
    if current_page < total_pages - 1:
        temp_data['page'] = current_page + 1
        db.save_temp_data(user_id, temp_data)
        
        await show_autoreply_chats_page(client, message, user_id, current_page + 1, total_pages)

@app.on_message(filters.text & filters.regex("^✅ Сохранить и продолжить$") & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'selecting_autoreply_chats'))
async def save_autoreply_chats(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    selected_chats = [chat for chat in temp_data['chats'] if chat.get('selected', False)]
    
    if not selected_chats:
        await message.reply_text("❌ Выберите хотя бы один чат.")
        return
    
    temp_data['selected_chats'] = selected_chats
    temp_data['step'] = 'entering_keywords'
    temp_data['temp_keywords'] = []
    db.save_temp_data(user_id, temp_data)
    
    await message.reply_text(
        f"✅ Выбрано чатов: {len(selected_chats)}\n\n"
        "📝 Введите ключевые слова для автоответа (по одному в сообщении).\n"
        "На эти слова будет срабатывать автоответчик.\n"
        "Когда закончите, отправьте /done_keywords\n\n"
        "Примеры: привет, здравствуй, hi",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("/done_keywords")], [KeyboardButton("❌ Отмена")]],
            resize_keyboard=True
        )
    )

# Обработчик для ввода ключевых слов
@app.on_message(filters.text & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'entering_keywords'))
async def handle_keyword_input(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text
    temp_data = db.get_temp_data(user_id)
    
    if text in ["/done_keywords", "❌ Отмена"]:
        return
    
    keywords = temp_data.get('temp_keywords', [])
    if len(keywords) < 20:  # Ограничение на количество ключевых слов
        keywords.append(text.lower().strip())
        temp_data['temp_keywords'] = keywords
        db.save_temp_data(user_id, temp_data)
        await message.reply_text(f"✅ Ключевое слово '{text}' сохранено. Отправьте следующее или /done_keywords")
    else:
        await message.reply_text("❌ Достигнут лимит ключевых слов (максимум 20)")

# Обработчик для ввода текста ответа
@app.on_message(filters.text & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'entering_reply_text'))
async def handle_reply_text_input(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text
    temp_data = db.get_temp_data(user_id)
    
    if text == "❌ Отмена":
        await cancel_action(client, message)
        return
    
    # Сохраняем автоответ
    account_id = temp_data.get('account_id')
    selected_chats = temp_data.get('selected_chats', [])
    keywords = temp_data.get('keywords', [])
    
    for chat in selected_chats:
        db.add_auto_reply(
            user_id,
            account_id,
            chat['chat_id'],
            chat['chat_title'],
            keywords,
            text
        )
    
    db.clear_temp_data(user_id)
    
    await message.reply_text(
        f"✅ Автоответчик успешно настроен для {len(selected_chats)} чатов!\n\n"
        f"Ключевые слова: {', '.join(keywords[:5])}"
        f"{'...' if len(keywords) > 5 else ''}\n"
        f"Ответ: {text[:100]}...",
        reply_markup=get_autoreply_keyboard()
    )

# Обработчик для удаления автоответа
@app.on_message(filters.text & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'deleting_autoreply'))
async def handle_delete_autoreply(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text
    temp_data = db.get_temp_data(user_id)
    
    if text.isdigit():
        index = int(text) - 1
        replies = temp_data.get('replies', [])
        
        if 0 <= index < len(replies):
            reply_to_delete = replies[index]
            db.delete_auto_reply(reply_to_delete['id'], user_id)
            db.clear_temp_data(user_id)
            
            await message.reply_text(
                f"✅ Автоответ для чата '{reply_to_delete['chat_title']}' удален.",
                reply_markup=get_autoreply_keyboard()
            )
        else:
            await message.reply_text("❌ Неверный номер. Попробуйте снова:")
    else:
        await message.reply_text("❌ Пожалуйста, отправьте номер автоответа:")

# Обработчик для входящих сообщений (автоответчик)
@app.on_message(filters.create(lambda _, __, m: m.chat.type != ChatType.PRIVATE and not m.from_user.is_self))
async def auto_reply_handler(client: Client, message: Message):
    """Обрабатывает входящие сообщения и отправляет автоответы"""
    
    # Пропускаем сообщения от самого себя
    if message.from_user and message.from_user.is_self:
        return
    
    chat_id = str(message.chat.id)
    user_id = None
    account_id = None
    
    # Ищем, какому пользователю принадлежит этот аккаунт
    # Это сложно определить напрямую, поэтому будем использовать костыль
    # В реальном проекте нужно хранить маппинг аккаунт-пользователь
    
    # Пока просто пропускаем, так как нужно доработать логику определения пользователя
    return

# Обработчики callback-запросов
@app.on_callback_query()
async def handle_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data == "buy_subscription":
        # Показываем тарифы
        text = "💎 Выберите тариф подписки:\n\n"
        text += "1 день - 3₽\n"
        text += "7 дней - 10₽\n"
        text += "Навсегда - 40₽\n\n"
        text += "Оплата через Crypto Bot\n"
        text += "Поддержка: @VestSoftSupport"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("1 день - 3₽", callback_data="plan_1day")],
            [InlineKeyboardButton("7 дней - 10₽", callback_data="plan_7days")],
            [InlineKeyboardButton("Навсегда - 40₽", callback_data="plan_forever")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_profile")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    
    elif data.startswith("plan_"):
        plan_type = data.replace("plan_", "")
        plan = SUBSCRIPTION_PLANS[plan_type]
        
        # Сохраняем выбранный план
        db.save_temp_data(user_id, {"selected_plan": plan_type})
        
        text = f"💎 Тариф: {plan['name']}\n"
        text += f"Цена: {plan['price_rub']}₽\n\n"
        text += "Выберите валюту для оплаты:\n\n"
        text += f"1 USDT = {EXCHANGE_RATES['USDT']}₽\n"
        text += f"1 TON = {EXCHANGE_RATES['TON']}₽"
        
        await callback_query.message.edit_text(text, reply_markup=get_payment_methods_keyboard())
    
    elif data == "pay_usdt":
        temp_data = db.get_temp_data(user_id)
        plan_type = temp_data.get("selected_plan")
        
        if not plan_type:
            await callback_query.answer("Ошибка выбора тарифа")
            return
        
        plan = SUBSCRIPTION_PLANS[plan_type]
        
        # Создаем счет в USDT
        invoice = await create_crypto_invoice(plan['price_rub'], "USDT", user_id, plan_type)
        
        if invoice:
            # Сохраняем информацию о платеже
            db.create_payment(
                user_id,
                invoice["invoice_id"],
                float(invoice["amount"]),
                "USDT",
                plan_type
            )
            
            text = f"💳 Счет на оплату создан!\n\n"
            text += f"Сумма: {invoice['amount']} USDT\n"
            text += f"Статус: ожидает оплаты\n\n"
            text += f"Ссылка для оплаты: {invoice['pay_url']}"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_invoice_{invoice['invoice_id']}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="buy_subscription")]
            ])
            
            await callback_query.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback_query.message.edit_text(
                "❌ Ошибка создания счета. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="buy_subscription")]])
            )
    
    elif data == "pay_ton":
        temp_data = db.get_temp_data(user_id)
        plan_type = temp_data.get("selected_plan")
        
        if not plan_type:
            await callback_query.answer("Ошибка выбора тарифа")
            return
        
        plan = SUBSCRIPTION_PLANS[plan_type]
        
        # Создаем счет в TON
        invoice = await create_crypto_invoice(plan['price_rub'], "TON", user_id, plan_type)
        
        if invoice:
            # Сохраняем информацию о платеже
            db.create_payment(
                user_id,
                invoice["invoice_id"],
                float(invoice["amount"]),
                "TON",
                plan_type
            )
            
            text = f"💳 Счет на оплату создан!\n\n"
            text += f"Сумма: {invoice['amount']} TON\n"
            text += f"Статус: ожидает оплаты\n\n"
            text += f"Ссылка для оплаты: {invoice['pay_url']}"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_invoice_{invoice['invoice_id']}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="buy_subscription")]
            ])
            
            await callback_query.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback_query.message.edit_text(
                "❌ Ошибка создания счета. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="buy_subscription")]])
            )
    
    elif data.startswith("check_invoice_"):
        invoice_id = data.replace("check_invoice_", "")
        
        # Проверяем статус счета
        status = await check_invoice_status(invoice_id)
        
        if status == "paid":
            # Получаем информацию о платеже из БД
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, plan_type FROM payments WHERE invoice_id = ?", (invoice_id,))
                row = cursor.fetchone()
                
                if row:
                    payment_user_id, plan_type = row
                    
                    # Активируем подписку
                    db.activate_subscription(payment_user_id, plan_type)
                    db.update_payment_status(invoice_id, "paid")
                    
                    await callback_query.message.edit_text(
                        "✅ Оплата прошла успешно! Подписка активирована.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👤 В профиль", callback_data="back_to_profile")]])
                    )
                else:
                    await callback_query.answer("Платеж не найден")
        elif status == "active":
            await callback_query.answer("Счет еще ожидает оплаты")
        else:
            await callback_query.answer("Не удалось проверить статус")
    
    elif data == "check_payment":
        # Показываем последние платежи пользователя
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
                (user_id,)
            )
            payments = cursor.fetchall()
        
        if not payments:
            await callback_query.answer("У вас нет активных платежей")
            return
        
        text = "📊 Ваши платежи:\n\n"
        for p in payments:
            status_text = "✅ Оплачен" if p[6] == "paid" else "⏳ Ожидает"
            text += f"• {p[4]} ({p[3]} {p[4]}) - {status_text}\n"
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_profile")]])
        )
    
    elif data == "back_to_profile":
        # Возвращаемся в профиль
        accounts = db.get_user_accounts(user_id)
        active_account = db.get_active_account(user_id)
        has_subscription = db.check_subscription(user_id)
        user_data = db.get_user(user_id)
        max_accounts = db.get_max_accounts(user_id)
        
        text = "👤 Ваш профиль\n\n"
        text += f"Telegram ID: `{user_id}`\n"
        text += f"Аккаунтов добавлено: {len(accounts)}/{max_accounts}\n\n"
        
        text += "💎 Статус подписки: "
        if has_subscription:
            if user_data["subscription_type"] == "forever":
                text += "Навсегда\n"
            elif user_data["subscription_end"]:
                end_date = datetime.fromisoformat(user_data["subscription_end"])
                days_left = (end_date - datetime.now()).days
                text += f"Активна (осталось {days_left} дн.)\n"
            else:
                text += "Активна\n"
        else:
            text += "Бесплатная\n"
            text += f"⚡ Лимит аккаунтов: {MAX_ACCOUNTS_FREE}\n\n"
        
        if active_account:
            text += f"\n✅ Активный аккаунт:\n"
            text += f"• {active_account['account_name']}\n"
            text += f"• {active_account['phone_number']}"
        else:
            text += "\n❌ Активный аккаунт не выбран"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Купить подписку", callback_data="buy_subscription")],
            [InlineKeyboardButton("🔄 Проверить оплату", callback_data="check_payment")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)

# Обработчик текстовых сообщений (для многошаговых сценариев)
@app.on_message(filters.text & ~filters.regex("^(📱 Менеджер аккаунтов|⚙️ Функции|👤 Профиль|➕ Добавить аккаунт|📋 Список аккаунтов|🔑 Выбрать активный аккаунт|❌ Удалить аккаунт|◀️ Назад в главное меню|◀️ Назад|◀️ Назад в функции|❌ Отмена|📨 Рассылка|🤖 Проверка спамблока|🔄 Автоответчик|📝 Установить автоответ|📋 Список автоответов|❌ Удалить автоответ|📥 Загрузить ещё чаты|✅ Завершить выбор и продолжить|📝 Ввести сообщения|✅ Запустить рассылку|⬅️ Назад|➡️ Вперед|✅ Сохранить и продолжить|/done|/done_keywords)$") & ~filters.regex("^🔄 Режим:.*$") & ~filters.regex("^⚡ Автоподписка:.*$") & ~filters.regex("^[⬜✅] .*$") & ~filters.regex("^✅ Начать проверку$"))
async def handle_text_input(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text
    temp_data = db.get_temp_data(user_id)
    
    step = temp_data.get('step')
    
    if step == "waiting_phone":
        phone = text.strip()
        if not phone.startswith('+'):
            phone = '+' + phone
        
        temp_data['phone'] = phone
        temp_data['step'] = "waiting_code"
        db.save_temp_data(user_id, temp_data)
        
        # Создаем временный клиент для авторизации
        try:
            # Создаем клиент для авторизации
            temp_client = Client(
                f"temp_{user_id}",
                api_id=BOT_API_ID,
                api_hash=BOT_API_HASH,
                in_memory=True
            )
            
            # Запускаем клиент и отправляем код
            await temp_client.connect()
            
            # Отправляем код подтверждения
            sent_code = await temp_client.send_code(phone)
            
            # Сохраняем клиент и данные во временные
            temp_data['temp_client'] = True
            temp_data['phone_code_hash'] = sent_code.phone_code_hash
            db.save_temp_data(user_id, temp_data)
            
            # Сохраняем клиент в глобальном словаре
            user_clients[f"temp_{user_id}"] = temp_client
            
            await message.reply_text(
                "✅ Код подтверждения отправлен на ваш телефон.\n\n"
                "✏️ Введите код из SMS:"
            )
            
        except PhoneNumberInvalid:
            await message.reply_text(
                "❌ Неверный формат номера телефона. Попробуйте снова.",
                reply_markup=get_account_manager_keyboard()
            )
            db.clear_temp_data(user_id)
        except Exception as e:
            await message.reply_text(
                f"❌ Ошибка: {str(e)}",
                reply_markup=get_account_manager_keyboard()
            )
            db.clear_temp_data(user_id)
    
    elif step == "waiting_code":
        code = text.strip()
        temp_data['code'] = code
        db.save_temp_data(user_id, temp_data)
        
        # Пытаемся завершить авторизацию
        temp_client = user_clients.get(f"temp_{user_id}")
        if not temp_client:
            await message.reply_text(
                "❌ Ошибка сессии. Начните заново.",
                reply_markup=get_account_manager_keyboard()
            )
            db.clear_temp_data(user_id)
            return
        
        try:
            # Пытаемся войти с кодом
            await temp_client.sign_in(
                phone_number=temp_data['phone'],
                phone_code_hash=temp_data['phone_code_hash'],
                phone_code=code
            )
            
            # Получаем session string
            session_string = await temp_client.export_session_string()
            
            # Сохраняем аккаунт в БД
            account_id = db.add_account(
                user_id,
                temp_data['phone'],
                session_string
            )
            
            # Если это первый аккаунт, делаем его активным
            accounts = db.get_user_accounts(user_id)
            if len(accounts) == 1:
                db.set_active_account(user_id, account_id)
                active_status = " и сделан активным"
            else:
                active_status = ""
            
            # Очищаем временные данные
            await temp_client.disconnect()
            if f"temp_{user_id}" in user_clients:
                del user_clients[f"temp_{user_id}"]
            db.clear_temp_data(user_id)
            
            await message.reply_text(
                f"✅ Аккаунт успешно добавлен{active_status}!",
                reply_markup=get_account_manager_keyboard()
            )
            
        except SessionPasswordNeeded:
            # Требуется двухфакторная аутентификация
            temp_data['step'] = "waiting_2fa"
            db.save_temp_data(user_id, temp_data)
            
            await message.reply_text(
                "🔐 Требуется двухфакторная аутентификация.\n\n"
                "Введите ваш пароль:"
            )
            
        except PhoneCodeInvalid:
            await message.reply_text(
                "❌ Неверный код. Попробуйте снова:"
            )
            
        except FloodWait as e:
            await message.reply_text(
                f"❌ Слишком много попыток. Подождите {e.value} секунд."
            )
            
        except Exception as e:
            await message.reply_text(
                f"❌ Ошибка: {str(e)}",
                reply_markup=get_account_manager_keyboard()
            )
            db.clear_temp_data(user_id)
    
    elif step == "waiting_2fa":
        password = text.strip()
        temp_client = user_clients.get(f"temp_{user_id}")
        
        if not temp_client:
            await message.reply_text("❌ Ошибка сессии.")
            return
        
        try:
            # Входим с паролем 2FA
            await temp_client.check_password(password)
            
            # Получаем session string
            session_string = await temp_client.export_session_string()
            
            # Сохраняем аккаунт
            account_id = db.add_account(
                user_id,
                temp_data['phone'],
                session_string
            )
            
            accounts = db.get_user_accounts(user_id)
            if len(accounts) == 1:
                db.set_active_account(user_id, account_id)
                active_status = " и сделан активным"
            else:
                active_status = ""
            
            await temp_client.disconnect()
            if f"temp_{user_id}" in user_clients:
                del user_clients[f"temp_{user_id}"]
            db.clear_temp_data(user_id)
            
            await message.reply_text(
                f"✅ Аккаунт успешно добавлен{active_status}!",
                reply_markup=get_account_manager_keyboard()
            )
            
        except Exception as e:
            await message.reply_text(
                f"❌ Ошибка: {str(e)}",
                reply_markup=get_cancel_keyboard()
            )
    
    elif step == "deleting_account":
        if text.isdigit():
            index = int(text) - 1
            accounts = temp_data.get('accounts', [])
            
            if 0 <= index < len(accounts):
                selected_account = accounts[index]
                db.delete_account(user_id, selected_account['id'])
                await stop_user_client(user_id, selected_account['id'])
                db.clear_temp_data(user_id)
                
                await message.reply_text(
                    f"✅ Аккаунт {selected_account['account_name']} удален.",
                    reply_markup=get_account_manager_keyboard()
                )
            else:
                await message.reply_text(
                    "❌ Неверный номер. Попробуйте снова:"
                )
        else:
            await message.reply_text(
                "❌ Пожалуйста, отправьте номер аккаунта (1, 2, 3...):"
            )
    
    elif step == "selecting_account":
        if text.isdigit():
            index = int(text) - 1
            accounts = temp_data.get('accounts', [])
            
            if 0 <= index < len(accounts):
                selected_account = accounts[index]
                db.set_active_account(user_id, selected_account['id'])
                db.clear_temp_data(user_id)
                
                await message.reply_text(
                    f"✅ Аккаунт {selected_account['account_name']} теперь активен.",
                    reply_markup=get_account_manager_keyboard()
                )
            else:
                await message.reply_text(
                    "❌ Неверный номер. Попробуйте снова:"
                )
        else:
            await message.reply_text(
                "❌ Пожалуйста, отправьте номер аккаунта (1, 2, 3...):"
            )
    
    elif step == "selecting_chats":
        # Проверяем, что ввели число (номер чата)
        if text.isdigit():
            chat_number = int(text)
            account_id = temp_data.get('account_id')
            offset = temp_data.get('offset', 0)
            
            if not account_id:
                await message.reply_text("❌ Ошибка. Начните заново.")
                return
            
            # Получаем чат по номеру
            chats = db.get_chats(user_id, account_id, 0, 1000)  # Получаем все чаты для поиска
            if 1 <= chat_number <= len(chats):
                selected_chat = chats[chat_number - 1]
                
                # Переключаем статус выбора
                new_status = not selected_chat['selected']
                db.select_chat(user_id, account_id, selected_chat['chat_id'], new_status)
                
                selected = db.get_selected_chats(user_id, account_id)
                if len(selected) > MAX_CHATS_PER_MAILING:
                    # Если выбрали слишком много, отменяем последний выбор
                    db.select_chat(user_id, account_id, selected_chat['chat_id'], False)
                    await message.reply_text(
                        f"❌ Нельзя выбрать больше {MAX_CHATS_PER_MAILING} чатов!"
                    )
                else:
                    status_text = "добавлен в список" if new_status else "удален из списка"
                    await message.reply_text(
                        f"✅ Чат '{selected_chat['chat_title']}' {status_text}.\n"
                        f"Выбрано: {len(selected)}/{MAX_CHATS_PER_MAILING}"
                    )
                
                # Показываем обновленную страницу
                await show_chats_page(client, message, user_id, account_id, offset)
            else:
                await message.reply_text(f"❌ Чат с номером {chat_number} не найден.")
        else:
            await message.reply_text("❌ Пожалуйста, отправьте номер чата.")
    
    elif step == "entering_messages":
        # Сохраняем сообщение
        messages = temp_data.get('temp_messages', [])
        if len(messages) < MAX_CHATS_PER_MAILING:
            messages.append(text)
            temp_data['temp_messages'] = messages
            db.save_temp_data(user_id, temp_data)
            await message.reply_text(f"✅ Сообщение {len(messages)} сохранено. Отправьте следующее или /done")
        else:
            await message.reply_text(f"❌ Достигнут лимит сообщений ({MAX_CHATS_PER_MAILING})")
    
    elif step == "waiting_message_count":
        if text.isdigit() and 1 <= int(text) <= MAX_CHATS_PER_MAILING:
            temp_data['message_count'] = int(text)
            temp_data['step'] = 'waiting_delay'
            db.save_temp_data(user_id, temp_data)
            
            await message.reply_text(
                f"✅ Будет отправлено {text} сообщений в каждый чат.\n\n"
                f"✏️ Введите задержку между сообщениями (в секундах, можно дробное число):"
            )
        else:
            await message.reply_text(f"❌ Введите число от 1 до {MAX_CHATS_PER_MAILING}:")
    
    elif step == "waiting_delay":
        try:
            delay = float(text)
            if delay < 0:
                raise ValueError()
            
            temp_data['delay'] = delay
            db.save_temp_data(user_id, temp_data)
            
            # Запускаем рассылку
            await execute_mailing(client, message, user_id, temp_data)
            
        except ValueError:
            await message.reply_text(
                "❌ Введите корректное число (например: 5 или 2.5):"
            )

# Обработчик для кнопок выбора аккаунтов при проверке спамблока
@app.on_message(filters.text & filters.regex(r"^[⬜✅] .* - .*$"))
async def handle_spamblock_account_selection(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'selecting_spamblock_accounts':
        return
    
    text = message.text
    # Убираем эмодзи в начале
    if text.startswith('✅ ') or text.startswith('⬜ '):
        text = text[2:]
    
    # Ищем аккаунт
    for acc in temp_data['accounts']:
        if acc['name'] in text and acc['phone'] in text:
            acc['selected'] = not acc['selected']
            db.save_temp_data(user_id, temp_data)
            
            # Обновляем клавиатуру
            await message.reply_text(
                f"{'✅' if acc['selected'] else '⬜'} Аккаунт {acc['name']} {'выбран' if acc['selected'] else 'отменен'}",
                reply_markup=get_spamblock_accounts_keyboard(temp_data['accounts'])
            )
            return

# Обработчик для кнопки "✅ Начать проверку" в спамблоке
@app.on_message(filters.text & filters.regex("^✅ Начать проверку$"))
async def start_spamblock_check(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'selecting_spamblock_accounts':
        return
    
    selected_accounts = [acc for acc in temp_data['accounts'] if acc['selected']]
    
    if not selected_accounts:
        await message.reply_text("❌ Выберите хотя бы один аккаунт")
        return
    
    if len(selected_accounts) > 10:
        await message.reply_text("❌ Можно выбрать не больше 10 аккаунтов")
        return
    
    await message.reply_text(
        "🔄 Начинаю проверку спамблока...",
        reply_markup=get_main_keyboard()
    )
    
    await check_spamblock(client, message, user_id, selected_accounts)
    db.clear_temp_data(user_id)

async def check_spamblock(client: Client, message: Message, user_id: int, selected_accounts: list):
    """Проверка спамблока для выбранных аккаунтов"""
    
    results = []
    
    for acc_data in selected_accounts:
        # Получаем полную информацию об аккаунте из БД
        accounts = db.get_user_accounts(user_id)
        account = next((a for a in accounts if a['id'] == acc_data['id']), None)
        
        if not account:
            results.append(f"❌ {acc_data['name']}: аккаунт не найден")
            continue
        
        user_client = await get_user_client(user_id, account)
        if not user_client:
            results.append(f"❌ {acc_data['name']}: не удалось подключиться")
            continue
        
        try:
            # Пытаемся найти диалог с @spambot
            spambot = await user_client.get_users("spambot")
            
            try:
                # Отправляем /start
                sent = await user_client.send_message(spambot.id, "/start")
                await asyncio.sleep(2)
                
                # Получаем ответ
                async for msg in user_client.get_chat_history(spambot.id, limit=1):
                    if msg.from_user and msg.from_user.is_self:
                        continue
                    # Копируем ответ бота
                    await client.send_message(
                        user_id,
                        f"🤖 {acc_data['name']}:\n\n{msg.text}"
                    )
                    results.append(f"✅ {acc_data['name']}: статус получен")
                    break
                    
            except UserIsBlocked:
                # Если бот заблокирован, разблокируем и пробуем снова
                await user_client.unblock_user(spambot.id)
                await asyncio.sleep(1)
                sent = await user_client.send_message(spambot.id, "/start")
                await asyncio.sleep(2)
                
                async for msg in user_client.get_chat_history(spambot.id, limit=1):
                    if msg.from_user and msg.from_user.is_self:
                        continue
                    await client.send_message(
                        user_id,
                        f"🤖 {acc_data['name']} (после разблокировки):\n\n{msg.text}"
                    )
                    results.append(f"✅ {acc_data['name']}: статус получен")
                    break
                    
        except Exception as e:
            results.append(f"❌ {acc_data['name']}: ошибка - {str(e)}")
    
    # Отправляем сводку
    summary = "📊 Результаты проверки спамблока:\n\n" + "\n".join(results)
    await client.send_message(user_id, summary)

async def execute_mailing(client: Client, message: Message, user_id: int, temp_data: dict):
    """Запуск рассылки"""
    account_id = temp_data.get('account_id')
    messages = temp_data.get('messages', [])
    chats = temp_data.get('chats', [])
    send_mode = temp_data.get('send_mode', 'sequential')
    message_count = temp_data.get('message_count', 1)
    delay = temp_data.get('delay', 1.0)
    auto_subscribe = temp_data.get('auto_subscribe', False)
    
    if not all([account_id, messages, chats, message_count, delay]):
        await message.reply_text("❌ Ошибка данных. Начните заново.")
        return
    
    active_account = db.get_active_account(user_id)
    if not active_account or active_account['id'] != account_id:
        await message.reply_text("❌ Аккаунт изменился. Начните заново.")
        return
    
    # Проверяем подписку
    has_subscription = db.check_subscription(user_id)
    
    # Если нет подписки, добавляем рекламный текст ко всем сообщениям
    if not has_subscription:
        messages = [msg + PROMO_TEXT for msg in messages]
        await client.send_message(
            user_id,
            "⚡ У вас бесплатная подписка. К сообщениям добавлена реклама бота.\n"
            "Купите подписку в профиле, чтобы убрать рекламу!"
        )
    
    user_client = await get_user_client(user_id, active_account)
    if not user_client:
        await message.reply_text("❌ Не удалось подключиться к аккаунту.")
        return
    
    # Создаем запись о рассылке в БД
    mailing_id = db.create_active_mailing(
        user_id, account_id, messages, chats, send_mode, 
        message_count, delay, auto_subscribe
    )
    
    await message.reply_text(
        "🚀 Запускаю рассылку...\n\n"
        f"Чатов: {len(chats)}\n"
        f"Сообщений в чат: {message_count}\n"
        f"Режим: {SEND_MODES[send_mode]}\n"
        f"Задержка: {delay} сек\n"
        f"Автоподписка: {'Вкл' if auto_subscribe else 'Выкл'}\n\n"
        "Я буду сообщать о прогрессе.",
        reply_markup=get_main_keyboard()
    )
    
    # Запускаем рассылку в зависимости от режима
    if send_mode == 'sequential':
        await sequential_mailing(client, user_id, user_client, mailing_id, 
                                 messages, chats, message_count, delay, auto_subscribe)
    else:
        await random_mailing(client, user_id, user_client, mailing_id,
                             messages, chats, message_count, delay, auto_subscribe)

async def sequential_mailing(client: Client, user_id: int, user_client: Client, mailing_id: int,
                            messages: List[str], chats: List[Dict], message_count: int, 
                            delay: float, auto_subscribe: bool):
    """Последовательная рассылка (сначала все в 1 чат, потом в другой)"""
    
    total_messages = len(chats) * message_count
    sent_messages = 0
    current_chat_index = 0
    current_message_index = 0
    
    for chat in chats:
        chat_title = chat['chat_title']
        chat_id = int(chat['chat_id'])
        current_chat_index += 1
        
        for msg_num in range(1, message_count + 1):
            try:
                # Выбираем случайное сообщение из списка
                message_text = random.choice(messages)
                
                # Отправляем сообщение
                sent = await user_client.send_message(chat_id, message_text)
                sent_messages += 1
                current_message_index = msg_num
                
                # Проверяем автоподписку, если включена
                if auto_subscribe and sent.reply_markup:
                    await check_and_process_buttons(
                        client, user_id, user_client, mailing_id,
                        chat_id, sent.id, sent.reply_markup
                    )
                
                # Отправляем прогресс каждые 5 сообщений
                if sent_messages % 5 == 0 or sent_messages == total_messages:
                    await client.send_message(
                        user_id,
                        f"📊 Прогресс: {sent_messages}/{total_messages}\n"
                        f"Текущий чат: {chat_title} ({msg_num}/{message_count})"
                    )
                
                # Обновляем прогресс в БД
                db.update_mailing_progress(mailing_id, current_chat_index, current_message_index, sent_messages)
                
                # Задержка между сообщениями
                await asyncio.sleep(delay)
                
            except FloodWait as e:
                wait_time = e.value
                await client.send_message(
                    user_id,
                    f"⚠️ Флуд контроль в чате {chat_title}. Ожидание {wait_time} секунд..."
                )
                await asyncio.sleep(wait_time)
                # Повторяем отправку
                message_text = random.choice(messages)
                sent = await user_client.send_message(chat_id, message_text)
                sent_messages += 1
                
                if auto_subscribe and sent.reply_markup:
                    await check_and_process_buttons(
                        client, user_id, user_client, mailing_id,
                        chat_id, sent.id, sent.reply_markup
                    )
                
            except PeerIdInvalid:
                await client.send_message(
                    user_id,
                    f"❌ Недействительный ID чата {chat_title}. Пропускаю..."
                )
                
            except Exception as e:
                await client.send_message(
                    user_id,
                    f"❌ Ошибка в чате {chat_title}: {str(e)}"
                )
            
            # Небольшая задержка после ошибок тоже
            await asyncio.sleep(1)
        
        # Небольшая задержка между чатами
        await asyncio.sleep(2)
    
    # Завершаем рассылку
    db.complete_mailing(mailing_id)
    
    # Проверяем, были ли задачи на автоподписку
    if auto_subscribe:
        pending_tasks = db.get_pending_auto_subscribe_tasks(mailing_id)
        if pending_tasks:
            await client.send_message(
                user_id,
                f"🔔 Найдено {len(pending_tasks)} задач на автоподписку. Обрабатываю..."
            )
            
            for task in pending_tasks:
                try:
                    # Нажимаем на кнопку
                    if task['button_data'] and task['button_data'].get('type') == 'callback':
                        await user_client.request_callback_answer(
                            chat_id=int(task['chat_id']),
                            message_id=task['message_id'],
                            callback_data=task['button_data']['data']
                        )
                    elif task['button_data'] and task['button_data'].get('type') == 'url':
                        # Для URL кнопок просто логируем
                        await client.send_message(
                            user_id,
                            f"🔗 Найдена ссылка для подписки: {task['button_data']['url']}"
                        )
                    
                    db.complete_auto_subscribe_task(task['id'])
                    
                    await client.send_message(
                        user_id,
                        f"✅ Выполнена подписка по кнопке в чате {task['chat_id']}"
                    )
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    await client.send_message(
                        user_id,
                        f"❌ Ошибка автоподписки: {str(e)}"
                    )
    
    await client.send_message(
        user_id,
        f"✅ Рассылка завершена!\n\n"
        f"Отправлено сообщений: {sent_messages}/{total_messages}",
        reply_markup=get_main_keyboard()
    )
    
    db.clear_temp_data(user_id)

async def random_mailing(client: Client, user_id: int, user_client: Client, mailing_id: int,
                        messages: List[str], chats: List[Dict], message_count: int, 
                        delay: float, auto_subscribe: bool):
    """Рандомная рассылка (случайный чат из выбранных)"""
    
    total_messages = len(chats) * message_count
    sent_messages = 0
    
    # Создаем список всех сообщений, которые нужно отправить
    all_messages_to_send = []
    for chat in chats:
        for _ in range(message_count):
            all_messages_to_send.append(chat)
    
    # Перемешиваем список
    random.shuffle(all_messages_to_send)
    
    current_message_index = 0
    
    for chat in all_messages_to_send:
        try:
            chat_title = chat['chat_title']
            chat_id = int(chat['chat_id'])
            current_message_index += 1
            
            # Выбираем случайное сообщение из списка
            message_text = random.choice(messages)
            
            # Отправляем сообщение
            sent = await user_client.send_message(chat_id, message_text)
            sent_messages += 1
            
            # Проверяем автоподписку, если включена
            if auto_subscribe and sent.reply_markup:
                await check_and_process_buttons(
                    client, user_id, user_client, mailing_id,
                    chat_id, sent.id, sent.reply_markup
                )
            
            # Отправляем прогресс каждые 5 сообщений
            if sent_messages % 5 == 0 or sent_messages == total_messages:
                await client.send_message(
                    user_id,
                    f"📊 Прогресс: {sent_messages}/{total_messages}\n"
                    f"Текущий чат: {chat_title}"
                )
            
            # Обновляем прогресс в БД
            db.update_mailing_progress(mailing_id, 0, current_message_index, sent_messages)
            
            # Задержка между сообщениями
            await asyncio.sleep(delay)
            
        except FloodWait as e:
            wait_time = e.value
            await client.send_message(
                user_id,
                f"⚠️ Флуд контроль. Ожидание {wait_time} секунд..."
            )
            await asyncio.sleep(wait_time)
            # Повторяем отправку
            message_text = random.choice(messages)
            sent = await user_client.send_message(chat_id, message_text)
            sent_messages += 1
            
            if auto_subscribe and sent.reply_markup:
                await check_and_process_buttons(
                    client, user_id, user_client, mailing_id,
                    chat_id, sent.id, sent.reply_markup
                )
            
        except PeerIdInvalid:
            await client.send_message(
                user_id,
                f"❌ Недействительный ID чата {chat_title}. Пропускаю..."
            )
            
        except Exception as e:
            await client.send_message(
                user_id,
                f"❌ Ошибка в чате {chat_title}: {str(e)}"
            )
        
        await asyncio.sleep(1)
    
    # Завершаем рассылку
    db.complete_mailing(mailing_id)
    
    # Проверяем, были ли задачи на автоподписку
    if auto_subscribe:
        pending_tasks = db.get_pending_auto_subscribe_tasks(mailing_id)
        if pending_tasks:
            await client.send_message(
                user_id,
                f"🔔 Найдено {len(pending_tasks)} задач на автоподписку. Обрабатываю..."
            )
            
            for task in pending_tasks:
                try:
                    # Нажимаем на кнопку
                    if task['button_data'] and task['button_data'].get('type') == 'callback':
                        await user_client.request_callback_answer(
                            chat_id=int(task['chat_id']),
                            message_id=task['message_id'],
                            callback_data=task['button_data']['data']
                        )
                    elif task['button_data'] and task['button_data'].get('type') == 'url':
                        # Для URL кнопок просто логируем
                        await client.send_message(
                            user_id,
                            f"🔗 Найдена ссылка для подписки: {task['button_data']['url']}"
                        )
                    
                    db.complete_auto_subscribe_task(task['id'])
                    
                    await client.send_message(
                        user_id,
                        f"✅ Выполнена подписка по кнопке в чате {task['chat_id']}"
                    )
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    await client.send_message(
                        user_id,
                        f"❌ Ошибка автоподписки: {str(e)}"
                    )
    
    await client.send_message(
        user_id,
        f"✅ Рассылка завершена!\n\n"
        f"Отправлено сообщений: {sent_messages}/{total_messages}",
        reply_markup=get_main_keyboard()
    )
    
    db.clear_temp_data(user_id)

async def check_and_process_buttons(client: Client, user_id: int, user_client: Client, mailing_id: int,
                                   chat_id: int, message_id: int, reply_markup):
    """Проверяет наличие кнопок и создает задачу на автоподписку"""
    
    try:
        # Проходим по всем кнопкам
        for row in reply_markup.inline_keyboard:
            for button in row:
                # Проверяем, ведет ли кнопка на подписку
                button_data = None
                
                if button.url and ("t.me" in button.url or "telegram" in button.url):
                    # Это ссылка на канал/группу
                    button_data = {
                        'type': 'url',
                        'url': button.url,
                        'text': button.text
                    }
                elif button.callback_data:
                    # Это callback кнопка
                    button_data = {
                        'type': 'callback',
                        'data': button.callback_data,
                        'text': button.text
                    }
                else:
                    continue
                
                # Сохраняем задачу в БД
                db.add_auto_subscribe_task(
                    user_id,
                    user_client.me.id,
                    mailing_id,
                    str(chat_id),
                    message_id,
                    json.dumps(button_data)
                )
                
                await client.send_message(
                    user_id,
                    f"🔍 Найдена кнопка для подписки в чате {chat_id}: {button.text}\n"
                    f"Будет обработано после завершения рассылки."
                )
                
    except Exception as e:
        print(f"Ошибка при проверке кнопок: {e}")

# Запуск бота
if __name__ == "__main__":
    print("🚀 Бот VEST SOFT запускается...")
    print(f"Бот API ID: {BOT_API_ID}")
    print(f"Токен бота загружен из переменных окружения")
    print("Ожидание подключения...")
    
    try:
        # Просто запускаем бота
        app.run()
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
