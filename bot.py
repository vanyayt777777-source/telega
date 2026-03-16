import os
import asyncio
import sqlite3
import json
import time
import random
import aiohttp
import re
import csv
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from collections import Counter
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import FloodWait, SessionPasswordNeeded, PhoneCodeInvalid, PhoneNumberInvalid, ApiIdInvalid
from pyrogram.errors import AccessTokenInvalid, UserIsBlocked, ChatAdminRequired, PeerIdInvalid, UsernameInvalid, UsernameOccupied, ChannelInvalid, AuthKeyUnregistered
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
MAX_CHATS_PER_REACTION = 3
MAX_MENTIONS_PER_STORY = 4
CHATS_PER_PAGE = 10
DATABASE_PATH = "vest_soft.db"

# Короткое рекламное сообщение (2 строки)
PROMO_TEXT = "\n━━━━━━━━━━━━━━\n🔥 @VestSoftBot 🔥\n━━━━━━━━━━━━━━"

# Режимы отправки
SEND_MODES = {
    "sequential": "📋 По очереди",
    "random": "🎲 Рандомно"
}

# Доступные реакции
AVAILABLE_REACTIONS = [
    {"emoji": "👍", "name": "👍 Лайк"},
    {"emoji": "👎", "name": "👎 Дизлайк"},
    {"emoji": "❤️", "name": "❤️ Сердечко"},
    {"emoji": "🔥", "name": "🔥 Огонь"},
    {"emoji": "🎉", "name": "🎉 Праздник"}
]

# Сообщения для прогрева
WARMUP_MESSAGES = [
    "Привет! Как дела?",
    "Что нового?",
    "Как настроение?",
    "Чем занимаешься?",
    "Отличный день сегодня!",
    "Как жизнь?",
    "Есть планы на вечер?",
    "Что думаешь о погоде?",
    "Давно не общались!",
    "Как прошел день?"
]

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
            [KeyboardButton("📱 Менеджер аккаунтов"), KeyboardButton("⚙️ Функции")],
            [KeyboardButton("👤 Мой профиль"), KeyboardButton("🛒 Купить аккаунт")]
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
            [KeyboardButton("🔄 Обновить данные")],
            [KeyboardButton("📂 Добавить из session файла")],
            [KeyboardButton("◀️ Назад в главное меню")]
        ],
        resize_keyboard=True
    )

def get_functions_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📨 Рассылка")],
            [KeyboardButton("📢 Создание каналов")],
            [KeyboardButton("👥 Создание групп")],
            [KeyboardButton("❤️ Масс-реакции")],
            [KeyboardButton("📱 Истории")],
            [KeyboardButton("🔍 Парсинг пользователей")],
            [KeyboardButton("🧠 Умный парсер")],
            [KeyboardButton("📊 Анализатор чатов")],
            [KeyboardButton("🔥 Прогрев аккаунтов")],
            [KeyboardButton("🤖 Проверка спамблока")],
            [KeyboardButton("◀️ Назад в главное меню")]
        ],
        resize_keyboard=True
    )

def get_reactions_keyboard():
    keyboard = []
    for reaction in AVAILABLE_REACTIONS:
        keyboard.append([KeyboardButton(reaction["name"])])
    keyboard.append([KeyboardButton("◀️ Назад")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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

def get_stop_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("⏹️ Остановить публикацию")]],
        resize_keyboard=True
    )

def get_chat_selection_keyboard(has_more: bool = False, max_chats: int = 100):
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
            [KeyboardButton("🔄 Режим: 📋 По очереди")],
            [KeyboardButton("⚡ Автоподписка: ❌ Выкл")],
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

def get_warmup_accounts_keyboard(accounts: list):
    keyboard = []
    for acc in accounts:
        status = "✅" if acc.get('selected', False) else "⬜"
        keyboard.append([KeyboardButton(f"{status} {acc['name']} - {acc['phone']}")])
    
    keyboard.append([KeyboardButton("✅ Начать прогрев")])
    keyboard.append([KeyboardButton("⏹️ Остановить прогрев")])
    keyboard.append([KeyboardButton("❌ Отмена")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_analyzer_choice_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📊 Активность")],
            [KeyboardButton("👥 Участники")],
            [KeyboardButton("📝 Сообщения")],
            [KeyboardButton("◀️ Назад")]
        ],
        resize_keyboard=True
    )

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
                    story_status TEXT DEFAULT 'idle',
                    auto_subscribe_enabled BOOLEAN DEFAULT 0,
                    channels_created INTEGER DEFAULT 0,
                    groups_created INTEGER DEFAULT 0,
                    messages_sent INTEGER DEFAULT 0,
                    reactions_set INTEGER DEFAULT 0,
                    users_parsed INTEGER DEFAULT 0,
                    smart_parsed INTEGER DEFAULT 0,
                    chats_analyzed INTEGER DEFAULT 0,
                    stories_posted INTEGER DEFAULT 0,
                    warmup_active BOOLEAN DEFAULT 0,
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
                    account_username TEXT,
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
            
            # Таблица для активных историй
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS active_stories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    account_id INTEGER,
                    media_path TEXT,
                    media_type TEXT,
                    caption TEXT,
                    mentions TEXT,
                    total_stories INTEGER,
                    current_story INTEGER DEFAULT 0,
                    delay REAL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для активных реакций
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS active_reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    account_id INTEGER,
                    chats TEXT,
                    reaction TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для прогрева аккаунтов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS warmup_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    account1_id INTEGER,
                    account2_id INTEGER,
                    status TEXT DEFAULT 'active',
                    message_count INTEGER DEFAULT 0,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для созданных каналов/групп
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS created_chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    account_id INTEGER,
                    chat_id TEXT,
                    chat_title TEXT,
                    chat_type TEXT,
                    username TEXT,
                    is_archived BOOLEAN DEFAULT 0,
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
                CREATE TABLE IF NOT EXISTS auto_subscribe_tasks (
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
            
            # Таблица для результатов парсинга
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parsed_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    account_id INTEGER,
                    chat_id TEXT,
                    chat_title TEXT,
                    user_id_parsed INTEGER UNIQUE,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    bio TEXT,
                    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для результатов умного парсинга
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS smart_parsed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    account_id INTEGER,
                    query TEXT,
                    result TEXT,
                    count INTEGER,
                    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                    "story_status": row[5],
                    "auto_subscribe_enabled": bool(row[6]),
                    "channels_created": row[7],
                    "groups_created": row[8],
                    "messages_sent": row[9],
                    "reactions_set": row[10],
                    "users_parsed": row[11],
                    "smart_parsed": row[12],
                    "chats_analyzed": row[13],
                    "stories_posted": row[14],
                    "warmup_active": bool(row[15]),
                    "created_at": row[16]
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
                    "account_username": row[5],
                    "is_active": bool(row[6]),
                    "is_blocked": bool(row[7]),
                    "block_date": row[8],
                    "created_at": row[9]
                })
            return accounts
    
    def update_account_username(self, account_id: int, username: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE accounts SET account_username = ? WHERE id = ?",
                (username, account_id)
            )
            conn.commit()
    
    def add_account(self, user_id: int, phone_number: str, session_string: str, username: str = "") -> int:
        accounts = self.get_user_accounts(user_id)
        account_name = f"Аккаунт {len(accounts) + 1}"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO accounts 
                   (user_id, phone_number, session_string, account_name, account_username) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, phone_number, session_string, account_name, username)
            )
            account_id = cursor.lastrowid
            conn.commit()
            return account_id
    
    def add_account_from_session(self, user_id: int, session_string: str, username: str = "") -> int:
        accounts = self.get_user_accounts(user_id)
        account_name = f"Аккаунт {len(accounts) + 1}"
        phone_number = "session_file"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO accounts 
                   (user_id, phone_number, session_string, account_name, account_username) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, phone_number, session_string, account_name, username)
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
                    "account_username": row[5],
                    "is_active": bool(row[6]),
                    "is_blocked": bool(row[7]),
                    "block_date": row[8],
                    "created_at": row[9]
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
    
    # Методы для историй
    def create_active_story(self, user_id: int, account_id: int, media_path: str, media_type: str,
                           caption: str, mentions: List[List[str]], total_stories: int, delay: float) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO active_stories 
                   (user_id, account_id, media_path, media_type, caption, mentions, total_stories, delay) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, account_id, media_path, media_type, caption, json.dumps(mentions), total_stories, delay)
            )
            story_id = cursor.lastrowid
            
            # Обновляем статус пользователя
            cursor.execute(
                "UPDATE users SET story_status = 'active' WHERE user_id = ?",
                (user_id,)
            )
            
            conn.commit()
            return story_id
    
    def get_active_story(self, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM active_stories WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "account_id": row[2],
                    "media_path": row[3],
                    "media_type": row[4],
                    "caption": row[5],
                    "mentions": json.loads(row[6]),
                    "total_stories": row[7],
                    "current_story": row[8],
                    "delay": row[9],
                    "status": row[10],
                    "created_at": row[11]
                }
            return None
    
    def update_story_progress(self, story_id: int, current_story: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE active_stories SET current_story = ? WHERE id = ?",
                (current_story, story_id)
            )
            conn.commit()
    
    def complete_story(self, story_id: int, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE active_stories SET status = 'completed' WHERE id = ?",
                (story_id,)
            )
            # Также обновляем статус пользователя
            cursor.execute(
                "UPDATE users SET story_status = 'idle', stories_posted = stories_posted + (SELECT current_story FROM active_stories WHERE id = ?) WHERE user_id = ?",
                (story_id, user_id)
            )
            conn.commit()
    
    # Методы для масс-реакций
    def create_active_reactions(self, user_id: int, account_id: int, chats: List[Dict], reaction: str) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO active_reactions 
                   (user_id, account_id, chats, reaction) 
                   VALUES (?, ?, ?, ?)""",
                (user_id, account_id, json.dumps(chats), reaction)
            )
            reaction_id = cursor.lastrowid
            conn.commit()
            return reaction_id
    
    def get_active_reactions(self, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM active_reactions WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "account_id": row[2],
                    "chats": json.loads(row[3]),
                    "reaction": row[4],
                    "status": row[5],
                    "created_at": row[6]
                }
            return None
    
    def stop_active_reactions(self, reaction_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE active_reactions SET status = 'stopped' WHERE id = ?",
                (reaction_id,)
            )
            conn.commit()
    
    # Методы для прогрева аккаунтов
    def create_warmup_session(self, user_id: int, account1_id: int, account2_id: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO warmup_sessions 
                   (user_id, account1_id, account2_id) 
                   VALUES (?, ?, ?)""",
                (user_id, account1_id, account2_id)
            )
            session_id = cursor.lastrowid
            cursor.execute(
                "UPDATE users SET warmup_active = 1 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
            return session_id
    
    def get_active_warmup_session(self, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM warmup_sessions WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "account1_id": row[2],
                    "account2_id": row[3],
                    "status": row[4],
                    "message_count": row[5],
                    "started_at": row[6]
                }
            return None
    
    def update_warmup_session(self, session_id: int, message_count: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE warmup_sessions SET message_count = ? WHERE id = ?",
                (message_count, session_id)
            )
            conn.commit()
    
    def stop_warmup_session(self, session_id: int, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE warmup_sessions SET status = 'stopped' WHERE id = ?",
                (session_id,)
            )
            cursor.execute(
                "UPDATE users SET warmup_active = 0 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
    
    def increment_messages_sent(self, user_id: int, count: int = 1):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET messages_sent = messages_sent + ? WHERE user_id = ?",
                (count, user_id)
            )
            conn.commit()
    
    def increment_reactions_set(self, user_id: int, count: int = 1):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET reactions_set = reactions_set + ? WHERE user_id = ?",
                (count, user_id)
            )
            conn.commit()
    
    def increment_users_parsed(self, user_id: int, count: int = 1):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET users_parsed = users_parsed + ? WHERE user_id = ?",
                (count, user_id)
            )
            conn.commit()
    
    def increment_smart_parsed(self, user_id: int, count: int = 1):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET smart_parsed = smart_parsed + ? WHERE user_id = ?",
                (count, user_id)
            )
            conn.commit()
    
    def increment_chats_analyzed(self, user_id: int, count: int = 1):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET chats_analyzed = chats_analyzed + ? WHERE user_id = ?",
                (count, user_id)
            )
            conn.commit()
    
    def increment_channels_created(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET channels_created = channels_created + 1 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
    
    def increment_groups_created(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET groups_created = groups_created + 1 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
    
    def save_created_chat(self, user_id: int, account_id: int, chat_id: str, chat_title: str, 
                          chat_type: str, username: str = "", is_archived: bool = False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO created_chats 
                   (user_id, account_id, chat_id, chat_title, chat_type, username, is_archived) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, account_id, chat_id, chat_title, chat_type, username, 1 if is_archived else 0)
            )
            conn.commit()
    
    def get_created_chats(self, user_id: int, account_id: Optional[int] = None) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if account_id:
                cursor.execute(
                    "SELECT * FROM created_chats WHERE user_id = ? AND account_id = ? ORDER BY created_at DESC",
                    (user_id, account_id)
                )
            else:
                cursor.execute(
                    "SELECT * FROM created_chats WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,)
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
                    "username": row[6],
                    "is_archived": bool(row[7]),
                    "created_at": row[8]
                })
            return chats
    
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
                """INSERT INTO auto_subscribe_tasks 
                   (user_id, account_id, mailing_id, chat_id, message_id, button_data) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, account_id, mailing_id, chat_id, message_id, button_data)
            )
            conn.commit()
    
    def get_pending_auto_subscribe_tasks(self, mailing_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM auto_subscribe_tasks WHERE mailing_id = ? AND status = 'pending'",
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
                "UPDATE auto_subscribe_tasks SET status = 'completed' WHERE id = ?",
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
    
    # Методы для парсинга пользователей
    def save_parsed_user(self, user_id: int, account_id: int, chat_id: str, chat_title: str,
                         user_id_parsed: int, username: str, first_name: str, last_name: str,
                         phone: str = "", bio: str = ""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """INSERT OR IGNORE INTO parsed_users 
                       (user_id, account_id, chat_id, chat_title, user_id_parsed, username, first_name, last_name, phone, bio) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, account_id, chat_id, chat_title, user_id_parsed, username, first_name, last_name, phone, bio)
                )
                conn.commit()
                return cursor.rowcount > 0
            except:
                return False
    
    def clear_parsed_users(self, user_id: int, account_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM parsed_users WHERE user_id = ? AND account_id = ?",
                (user_id, account_id)
            )
            conn.commit()
    
    def get_parsed_users_count(self, user_id: int, account_id: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM parsed_users WHERE user_id = ? AND account_id = ?",
                (user_id, account_id)
            )
            return cursor.fetchone()[0]
    
    # Методы для умного парсинга
    def save_smart_parsed(self, user_id: int, account_id: int, query: str, result: str, count: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO smart_parsed 
                   (user_id, account_id, query, result, count) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, account_id, query, result, count)
            )
            conn.commit()
            return cursor.lastrowid

# Инициализация базы данных
db = Database()

# Временные клиенты для аккаунтов пользователей
user_clients = {}
# Словарь для отслеживания активных реакций
active_reaction_tasks = {}
# Словарь для отслеживания активных задач парсинга
active_parse_tasks = {}
# Словарь для отслеживания активных задач прогрева
active_warmup_tasks = {}
# Словарь для отслеживания активных задач анализа
active_analyzer_tasks = {}
# Словарь для отслеживания активных задач публикации историй
active_story_tasks = {}

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
        # Получаем и сохраняем username аккаунта
        me = await client.get_me()
        if me.username and not account.get('account_username'):
            db.update_account_username(account['id'], me.username)
        
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
    
    welcome_text = (
        "🌟 **Добро пожаловать в VEST SOFT Bot!** 🌟\n\n"
        "Я помогу вам управлять несколькими Telegram аккаунтами\n"
        "и делать массовые рассылки по чатам.\n\n"
        "**🔥 Наши возможности:**\n"
        "✓ Управление аккаунтами\n"
        "✓ Массовая рассылка\n"
        "✓ Создание каналов и групп\n"
        "✓ Масс-реакции на сообщения\n"
        "✓ Публикация историй\n"
        "✓ Прогрев аккаунтов\n"
        "✓ Парсинг пользователей\n"
        "✓ Умный парсер\n"
        "✓ Анализатор чатов\n"
        "✓ Проверка спам-блока\n"
        "✓ Автоподписка\n\n"
        "📢 **Наш канал:** @VestSoftTG\n"
        "💬 **Поддержка:** @VestSoftSupport\n\n"
        "Используйте кнопки меню для навигации. 👇"
    )
    
    await message.reply_text(
        welcome_text,
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

@app.on_message(filters.command("stop_reactions"))
async def stop_reactions_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Останавливаем активные реакции
    if user_id in active_reaction_tasks:
        active_reaction_tasks[user_id] = False
        del active_reaction_tasks[user_id]
        
        # Обновляем статус в БД
        active_reactions = db.get_active_reactions(user_id)
        if active_reactions:
            db.stop_active_reactions(active_reactions['id'])
        
        await message.reply_text(
            "✅ **Масс-реакции остановлены!**",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.reply_text(
            "❌ **У вас нет активных масс-реакций.**",
            reply_markup=get_main_keyboard()
        )

@app.on_message(filters.command("stop_warmup"))
async def stop_warmup_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id in active_warmup_tasks:
        active_warmup_tasks[user_id] = False
        del active_warmup_tasks[user_id]
        
        # Обновляем статус в БД
        warmup_session = db.get_active_warmup_session(user_id)
        if warmup_session:
            db.stop_warmup_session(warmup_session['id'], user_id)
        
        await message.reply_text(
            "✅ **Прогрев аккаунтов остановлен!**",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.reply_text(
            "❌ **У вас нет активного прогрева.**",
            reply_markup=get_main_keyboard()
        )

@app.on_message(filters.command("stopparse"))
async def stop_parse_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id in active_parse_tasks:
        active_parse_tasks[user_id] = False
        del active_parse_tasks[user_id]
        
        await message.reply_text(
            "✅ **Парсинг остановлен!**",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.reply_text(
            "❌ **У вас нет активного парсинга.**",
            reply_markup=get_main_keyboard()
        )

@app.on_message(filters.command("stop_analyzer"))
async def stop_analyzer_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id in active_analyzer_tasks:
        active_analyzer_tasks[user_id] = False
        del active_analyzer_tasks[user_id]
        
        await message.reply_text(
            "✅ **Анализ остановлен!**",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.reply_text(
            "❌ **У вас нет активного анализа.**",
            reply_markup=get_main_keyboard()
        )

@app.on_message(filters.command("stop_story"))
async def stop_story_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id in active_story_tasks:
        active_story_tasks[user_id] = False
        del active_story_tasks[user_id]
        
        # Обновляем статус в БД
        active_story = db.get_active_story(user_id)
        if active_story:
            db.complete_story(active_story['id'], user_id)
        
        await message.reply_text(
            "✅ **Публикация историй остановлена!**",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.reply_text(
            "❌ **У вас нет активной публикации историй.**",
            reply_markup=get_main_keyboard()
        )

# Обработчики навигации
@app.on_message(filters.text & filters.regex("^📱 Менеджер аккаунтов$"))
async def account_manager_menu(client: Client, message: Message):
    text = (
        "📱 **Менеджер аккаунтов**\n\n"
        "Здесь вы можете управлять своими Telegram аккаунтами:\n"
        "• Добавлять новые аккаунты по номеру\n"
        "• Добавлять аккаунты из session файлов\n"
        "• Просматривать список\n"
        "• Выбирать активный аккаунт\n"
        "• Удалять ненужные\n"
        "• Обновлять данные\n\n"
        "Выберите действие: 👇"
    )
    
    await message.reply_text(
        text,
        reply_markup=get_account_manager_keyboard()
    )

@app.on_message(filters.text & filters.regex("^⚙️ Функции$"))
async def functions_menu(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ **Сначала выберите активный аккаунт!**\n\n"
            "Используйте кнопку '🔑 Выбрать активный аккаунт' в менеджере аккаунтов.",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    await message.reply_text(
        f"⚙️ **Функции**\n\n"
        f"**Активный аккаунт:** {active_account['account_name']}\n"
        f"📱 `{active_account['phone_number']}`\n\n"
        f"**Доступные функции:**\n"
        f"• 📨 Рассылка по чатам\n"
        f"• 📢 Создание каналов\n"
        f"• 👥 Создание групп\n"
        f"• ❤️ Масс-реакции на сообщения\n"
        f"• 📱 Истории\n"
        f"• 🔍 Парсинг пользователей\n"
        f"• 🧠 Умный парсер\n"
        f"• 📊 Анализатор чатов\n"
        f"• 🔥 Прогрев аккаунтов\n"
        f"• 🤖 Проверка спам-блока\n\n"
        f"Выберите функцию: 👇",
        reply_markup=get_functions_keyboard()
    )

@app.on_message(filters.text & filters.regex("^👤 Мой профиль$"))
async def profile_menu(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    active_account = db.get_active_account(user_id)
    has_subscription = db.check_subscription(user_id)
    user_data = db.get_user(user_id)
    max_accounts = db.get_max_accounts(user_id)
    created_chats = db.get_created_chats(user_id)
    
    channels = [c for c in created_chats if c['chat_type'] == 'channel']
    groups = [c for c in created_chats if c['chat_type'] == 'group']
    
    # Информация о подписке
    if has_subscription:
        if user_data["subscription_type"] == "forever":
            sub_status = "💎 **Навсегда**"
        elif user_data["subscription_end"]:
            end_date = datetime.fromisoformat(user_data["subscription_end"])
            days_left = (end_date - datetime.now()).days
            sub_status = f"✅ **Активна** (осталось {days_left} дн.)"
        else:
            sub_status = "✅ **Активна**"
    else:
        sub_status = "❌ **Бесплатная**"
    
    text = (
        "👤 **Ваш профиль**\n\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"📱 **Аккаунтов:** {len(accounts)}/{max_accounts}\n"
        f"💎 **Подписка:** {sub_status}\n"
        f"📨 **Сообщений отправлено:** {user_data['messages_sent']}\n"
        f"❤️ **Реакций поставлено:** {user_data['reactions_set']}\n"
        f"📱 **Историй опубликовано:** {user_data['stories_posted']}\n"
        f"🔍 **Пользователей спарсено:** {user_data['users_parsed']}\n"
        f"🧠 **Умный парсер:** {user_data['smart_parsed']}\n"
        f"📊 **Чатов проанализировано:** {user_data['chats_analyzed']}\n"
        f"📢 **Создано каналов:** {len(channels)}\n"
        f"👥 **Создано групп:** {len(groups)}\n"
        f"🔥 **Прогрев активен:** {'✅ Да' if user_data['warmup_active'] else '❌ Нет'}\n"
        f"📅 **Регистрация:** {user_data['created_at'][:10]}\n\n"
    )
    
    if active_account:
        username_info = f" (@{active_account['account_username']})" if active_account['account_username'] else ""
        text += (
            f"✅ **Активный аккаунт:**\n"
            f"• **{active_account['account_name']}**{username_info}\n"
            f"• 📱 `{active_account['phone_number']}`\n"
        )
    else:
        text += "❌ **Активный аккаунт не выбран**\n"
    
    text += "\n📢 **Наш канал:** @VestSoftTG"
    
    # Добавляем кнопки для покупки подписки
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Купить подписку", callback_data="buy_subscription")],
        [InlineKeyboardButton("🔄 Проверить оплату", callback_data="check_payment")]
    ])
    
    await message.reply_text(
        text,
        reply_markup=keyboard
    )

@app.on_message(filters.text & filters.regex("^🛒 Купить аккаунт$"))
async def buy_account_menu(client: Client, message: Message):
    text = (
        "🛒 **Купить аккаунт Telegram**\n\n"
        "У нас вы также можете приобрести готовые аккаунты для рассылки и других целей:\n\n"
        "📱 **ФИЗ аккаунты** – аккаунты, зарегистрированные на реальные SIM-карты\n"
        "🔥 **Прогретые аккаунты** – аккаунты с историей, готовые к работе\n"
        "⏳ **Аккаунты с отлежкой** – аккаунты, которые прошли необходимый срок после регистрации\n\n"
        "➡️ **Купить: @VestAccountsBot**\n\n"
        "Переходите и выбирайте подходящие аккаунты для ваших задач! 👆"
    )
    
    # Создаем инлайн кнопку для перехода
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Перейти в магазин", url="https://t.me/VestAccountsBot")]
    ])
    
    await message.reply_text(
        text,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

@app.on_message(filters.text & filters.regex("^◀️ Назад в главное меню$|^◀️ Назад$"))
async def back_to_main(client: Client, message: Message):
    user_id = message.from_user.id
    db.clear_temp_data(user_id)
    await message.reply_text(
        "🏠 **Главное меню:**",
        reply_markup=get_main_keyboard()
    )

@app.on_message(filters.text & filters.regex("^❌ Отмена$"))
async def cancel_action(client: Client, message: Message):
    user_id = message.from_user.id
    db.clear_temp_data(user_id)
    await message.reply_text(
        "❌ **Действие отменено.**",
        reply_markup=get_main_keyboard()
    )

# Управление аккаунтами
@app.on_message(filters.text & filters.regex("^📋 Список аккаунтов$"))
async def list_accounts(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    max_accounts = db.get_max_accounts(user_id)
    
    if not accounts:
        await message.reply_text(
            "📋 **У вас пока нет добавленных аккаунтов.**\n\n"
            "➕ Нажмите 'Добавить аккаунт', чтобы начать.",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    text = "📋 **Список ваших аккаунтов:**\n\n"
    for acc in accounts:
        status = "✅ **АКТИВЕН**" if acc['is_active'] else "❌ не активен"
        block_status = " 🔴 ЗАБЛОКИРОВАН" if acc['is_blocked'] else ""
        username_info = f" (@{acc['account_username']})" if acc['account_username'] else ""
        phone_display = "session файл" if acc['phone_number'] == "session_file" else acc['phone_number']
        
        text += f"• **{acc['account_name']}**{username_info}\n"
        text += f"  📱 `{phone_display}`\n"
        text += f"  {status}{block_status}\n"
        text += f"  🆔 ID: `{acc['id']}`\n\n"
    
    text += f"📊 **Всего аккаунтов:** {len(accounts)}/{max_accounts}"
    
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
            f"❌ **Вы достигли лимита в {max_accounts} аккаунтов.**\n\n"
            f"💎 Купите подписку в профиле, чтобы увеличить лимит до {MAX_ACCOUNTS_PAID} аккаунтов!",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    db.save_temp_data(user_id, {"step": "waiting_phone"})
    
    await message.reply_text(
        "📱 **Для добавления аккаунта введите номер телефона**\n"
        "в международном формате:\n\n"
        "Пример: `+79001234567`\n\n"
        "Или нажмите 'Отмена' для выхода.",
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.text & filters.regex("^📂 Добавить из session файла$"))
async def add_account_from_session_start(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    max_accounts = db.get_max_accounts(user_id)
    
    if len(accounts) >= max_accounts:
        await message.reply_text(
            f"❌ **Вы достигли лимита в {max_accounts} аккаунтов.**\n\n"
            f"💎 Купите подписку в профиле, чтобы увеличить лимит до {MAX_ACCOUNTS_PAID} аккаунтов!",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    db.save_temp_data(user_id, {"step": "waiting_session_file"})
    
    await message.reply_text(
        "📂 **Отправьте файл session.pyrogram**\n\n"
        "Это должен быть файл сессии, экспортированный из Telegram.\n\n"
        "Или нажмите 'Отмена' для выхода.",
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.document & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'waiting_session_file'))
async def handle_session_file(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if not message.document:
        await message.reply_text("❌ **Это не файл!** Пожалуйста, отправьте файл .session")
        return
    
    if not message.document.file_name.endswith('.session'):
        await message.reply_text("❌ **Неверный формат файла!** Нужен файл с расширением .session")
        return
    
    # Скачиваем файл
    file_path = await message.download()
    
    try:
        # Читаем содержимое файла
        with open(file_path, 'r', encoding='utf-8') as f:
            session_string = f.read().strip()
        
        # Пробуем создать временный клиент для получения информации
        temp_client = Client(
            f"temp_session_{user_id}",
            api_id=BOT_API_ID,
            api_hash=BOT_API_HASH,
            session_string=session_string,
            in_memory=True
        )
        
        await temp_client.start()
        me = await temp_client.get_me()
        await temp_client.stop()
        
        # Сохраняем аккаунт
        account_id = db.add_account_from_session(
            user_id,
            session_string,
            me.username or ""
        )
        
        # Если это первый аккаунт, делаем его активным
        accounts = db.get_user_accounts(user_id)
        if len(accounts) == 1:
            db.set_active_account(user_id, account_id)
            active_status = " и сделан активным"
        else:
            active_status = ""
        
        await message.reply_text(
            f"✅ **Аккаунт успешно добавлен{active_status}!**\n\n"
            f"👤 Имя: {me.first_name}\n"
            f"🔗 Username: @{me.username}" if me.username else "",
            reply_markup=get_account_manager_keyboard()
        )
        
    except Exception as e:
        await message.reply_text(
            f"❌ **Ошибка при загрузке сессии:**\n`{str(e)}`\n\n"
            f"Убедитесь, что файл корректен.",
            reply_markup=get_account_manager_keyboard()
        )
    finally:
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)
        
        db.clear_temp_data(user_id)

@app.on_message(filters.text & filters.regex("^❌ Удалить аккаунт$"))
async def delete_account_menu(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await message.reply_text(
            "❌ **У вас нет добавленных аккаунтов.**",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    # Сохраняем список аккаунтов во временные данные
    db.save_temp_data(user_id, {"step": "deleting_account", "accounts": accounts})
    
    text = "❌ **Выберите аккаунт для удаления:**\n\n"
    for i, acc in enumerate(accounts, 1):
        phone_display = "session файл" if acc['phone_number'] == "session_file" else acc['phone_number']
        text += f"{i}. **{acc['account_name']}** - `{phone_display}`\n"
    text += "\n📝 **Отправьте номер аккаунта** (1, 2, 3...) или нажмите Отмена"
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.text & filters.regex("^🔄 Обновить данные$"))
async def refresh_account_data(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await message.reply_text(
            "❌ **У вас нет добавленных аккаунтов.**",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    await message.reply_text(
        "🔄 **Обновляю данные аккаунтов...**\n\n"
        "Это может занять некоторое время.",
        reply_markup=get_back_keyboard()
    )
    
    updated = 0
    for account in accounts:
        user_client = await get_user_client(user_id, account)
        if user_client:
            try:
                me = await user_client.get_me()
                if me.username != account.get('account_username'):
                    db.update_account_username(account['id'], me.username or "")
                    updated += 1
            except:
                pass
    
    await message.reply_text(
        f"✅ **Обновление завершено!**\n\n"
        f"Обновлено аккаунтов: {updated}",
        reply_markup=get_account_manager_keyboard()
    )

@app.on_message(filters.text & filters.regex("^🔑 Выбрать активный аккаунт$"))
async def select_active_account_menu(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await message.reply_text(
            "❌ **У вас нет добавленных аккаунтов.**",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    # Сохраняем список аккаунтов во временные данные
    db.save_temp_data(user_id, {"step": "selecting_account", "accounts": accounts})
    
    text = "🔑 **Выберите активный аккаунт:**\n\n"
    for i, acc in enumerate(accounts, 1):
        status = " ✅ **(текущий)**" if acc['is_active'] else ""
        phone_display = "session файл" if acc['phone_number'] == "session_file" else acc['phone_number']
        text += f"{i}. **{acc['account_name']}** - `{phone_display}`{status}\n"
    text += "\n📝 **Отправьте номер аккаунта** (1, 2, 3...) или нажмите Отмена"
    
    await message.reply_text(
        text,
        reply_markup=get_cancel_keyboard()
    )

# Функция Истории
@app.on_message(filters.text & filters.regex("^📱 Истории$"))
async def stories_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ **Сначала выберите активный аккаунт!**",
            reply_markup=get_functions_keyboard()
        )
        return
    
    # Проверяем, не запущена ли уже публикация
    active_story = db.get_active_story(user_id)
    if active_story:
        await message.reply_text(
            "⚠️ **У вас уже есть активная публикация историй!**\n\n"
            f"Опубликовано {active_story['current_story']}/{active_story['total_stories']}\n"
            f"Отправьте /stop_story чтобы остановить.",
            reply_markup=get_main_keyboard()
        )
        return
    
    db.save_temp_data(user_id, {
        "step": "waiting_story_media",
        "account_id": active_account['id']
    })
    
    await message.reply_text(
        "📱 **Публикация историй**\n\n"
        "Отправьте медиафайл для истории (фото или видео):\n\n"
        "Поддерживаются:\n"
        "• Фото (JPEG, PNG)\n"
        "• Видео (MP4)\n\n"
        "Или нажмите 'Отмена' для выхода.",
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.photo | filters.video & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'waiting_story_media'))
async def handle_story_media(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    # Сохраняем медиафайл
    file_path = await message.download()
    
    media_type = "photo" if message.photo else "video"
    
    temp_data['media_path'] = file_path
    temp_data['media_type'] = media_type
    temp_data['step'] = 'waiting_story_caption'
    db.save_temp_data(user_id, temp_data)
    
    await message.reply_text(
        "✅ **Медиафайл сохранен!**\n\n"
        "📝 Теперь отправьте текстовое описание к истории:\n\n"
        "Этот текст будет отображаться под историей.\n"
        "Можно отправить пустое сообщение, если описание не нужно.",
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.text & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'waiting_story_caption'))
async def handle_story_caption(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    caption = message.text if message.text != "❌ Отмена" else ""
    
    temp_data['caption'] = caption
    temp_data['step'] = 'waiting_story_mentions_file'
    db.save_temp_data(user_id, temp_data)
    
    await message.reply_text(
        f"✅ **Описание сохранено!**\n\n"
        f"📄 Теперь отправьте **TXT файл** со списком людей для отметки.\n\n"
        f"Формат файла:\n"
        f"`ID | username | имя | фамилия`\n\n"
        f"Бот автоматически извлечет только username.\n"
        f"Максимум {MAX_MENTIONS_PER_STORY} отметок в одной истории.\n\n"
        f"Если в файле больше людей, они будут разбиты на несколько историй.",
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.document & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'waiting_story_mentions_file'))
async def handle_story_mentions_file(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if not message.document.file_name.endswith('.txt'):
        await message.reply_text("❌ **Пожалуйста, отправьте файл с расширением .txt**")
        return
    
    # Скачиваем файл
    file_path = await message.download()
    
    try:
        # Читаем файл и извлекаем username
        all_mentions = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '|' in line:
                    parts = line.strip().split('|')
                    if len(parts) >= 2:
                        username = parts[1].strip()
                        # Убираем @ если есть
                        if username.startswith('@'):
                            username = username[1:]
                        if username and username not in all_mentions:
                            all_mentions.append(username)
        
        if not all_mentions:
            await message.reply_text("❌ **Не найдено username в файле!**")
            os.remove(file_path)
            return
        
        # Разбиваем на группы по MAX_MENTIONS_PER_STORY
        mention_groups = []
        for i in range(0, len(all_mentions), MAX_MENTIONS_PER_STORY):
            group = all_mentions[i:i + MAX_MENTIONS_PER_STORY]
            mention_groups.append(group)
        
        temp_data['mentions'] = mention_groups
        temp_data['total_stories'] = len(mention_groups)
        temp_data['mentions_file'] = file_path
        temp_data['step'] = 'waiting_story_delay'
        db.save_temp_data(user_id, temp_data)
        
        await message.reply_text(
            f"✅ **Файл обработан!**\n\n"
            f"📊 Найдено username: {len(all_mentions)}\n"
            f"📱 Будет создано историй: {len(mention_groups)}\n\n"
            f"⏱️ Введите задержку между историями (в секундах):",
            reply_markup=get_cancel_keyboard()
        )
        
    except Exception as e:
        await message.reply_text(f"❌ **Ошибка при обработке файла:**\n`{str(e)}`")
        if os.path.exists(file_path):
            os.remove(file_path)

@app.on_message(filters.text & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'waiting_story_delay'))
async def handle_story_delay(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    try:
        delay = float(message.text)
        if delay < 0:
            raise ValueError()
        
        temp_data['delay'] = delay
        db.save_temp_data(user_id, temp_data)
        
        # Показываем сводку и запрашиваем подтверждение
        await show_story_summary(client, message, user_id, temp_data)
        
    except ValueError:
        await message.reply_text("❌ **Введите корректное число** (например: 5 или 2.5):")

async def show_story_summary(client: Client, message: Message, user_id: int, temp_data: dict):
    """Показывает сводку по историям и запрашивает подтверждение"""
    
    media_type = "Фото" if temp_data['media_type'] == "photo" else "Видео"
    caption = temp_data['caption'] if temp_data['caption'] else "Без описания"
    total_stories = temp_data['total_stories']
    delay = temp_data['delay']
    
    text = (
        "📱 **Сводка по историям**\n\n"
        f"📁 Тип медиа: {media_type}\n"
        f"📝 Описание: {caption[:50]}..." if len(caption) > 50 else f"📝 Описание: {caption}\n"
        f"📊 Всего историй: {total_stories}\n"
        f"👥 Отметок в истории: до {MAX_MENTIONS_PER_STORY}\n"
        f"⏱️ Задержка: {delay} сек\n\n"
        f"✅ **Начать публикацию?**\n\n"
        f"Отправьте 'да' для запуска или 'нет' для отмены."
    )
    
    temp_data['step'] = 'waiting_story_confirmation'
    db.save_temp_data(user_id, temp_data)
    
    await message.reply_text(text, reply_markup=get_cancel_keyboard())

@app.on_message(filters.text & filters.create(lambda _, __, m: db.get_temp_data(m.from_user.id).get('step') == 'waiting_story_confirmation'))
async def handle_story_confirmation(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.lower().strip()
    temp_data = db.get_temp_data(user_id)
    
    if text == "да":
        await start_story_publishing(client, message, user_id, temp_data)
    else:
        # Очищаем временные файлы
        if os.path.exists(temp_data.get('media_path', '')):
            os.remove(temp_data['media_path'])
        if os.path.exists(temp_data.get('mentions_file', '')):
            os.remove(temp_data['mentions_file'])
        
        db.clear_temp_data(user_id)
        await message.reply_text("❌ **Публикация отменена.**", reply_markup=get_functions_keyboard())

async def start_story_publishing(client: Client, message: Message, user_id: int, temp_data: dict):
    """Запускает публикацию историй"""
    
    account_id = temp_data.get('account_id')
    media_path = temp_data.get('media_path')
    media_type = temp_data.get('media_type')
    caption = temp_data.get('caption', '')
    mention_groups = temp_data.get('mentions', [])
    total_stories = temp_data.get('total_stories', 0)
    delay = temp_data.get('delay', 5)
    
    if not all([account_id, media_path, mention_groups, total_stories]):
        await message.reply_text("❌ Ошибка данных. Начните заново.")
        return
    
    active_account = db.get_active_account(user_id)
    if not active_account or active_account['id'] != account_id:
        await message.reply_text("❌ **Активный аккаунт изменился!**\nНачните заново.")
        return
    
    user_client = await get_user_client(user_id, active_account)
    if not user_client:
        await message.reply_text("❌ Не удалось подключиться к аккаунту.")
        return
    
    # Создаем запись в БД
    story_id = db.create_active_story(
        user_id, account_id, media_path, media_type, caption, mention_groups, total_stories, delay
    )
    
    await message.reply_text(
        f"📱 **Начинаю публикацию историй...**\n\n"
        f"📊 Всего историй: {total_stories}\n"
        f"⏱️ Задержка: {delay} сек\n\n"
        f"Отправьте /stop_story чтобы остановить.",
        reply_markup=get_stop_keyboard()
    )
    
    active_story_tasks[user_id] = True
    current_story = 0
    
    try:
        for i, mentions in enumerate(mention_groups, 1):
            if not active_story_tasks.get(user_id, False):
                await client.send_message(
                    user_id,
                    "⏹️ **Публикация остановлена пользователем.**"
                )
                break
            
            try:
                # Формируем упоминания
                mention_text = ""
                if mentions:
                    mention_text = " ".join([f"@{username}" for username in mentions])
                    if caption:
                        final_caption = f"{caption}\n\n{mention_text}"
                    else:
                        final_caption = mention_text
                else:
                    final_caption = caption
                
                # Публикуем историю
                if media_type == "photo":
                    await user_client.send_photo(
                        "me",
                        photo=media_path,
                        caption=final_caption
                    )
                else:
                    await user_client.send_video(
                        "me",
                        video=media_path,
                        caption=final_caption
                    )
                
                current_story = i
                db.update_story_progress(story_id, current_story)
                
                # Отправляем прогресс
                await client.send_message(
                    user_id,
                    f"✅ **История {i}/{total_stories} опубликована**\n"
                    f"👥 Отмечено: {len(mentions)} человек"
                )
                
                # Ждем перед следующей историей
                if i < total_stories:
                    await asyncio.sleep(delay)
                
            except FloodWait as e:
                wait_time = e.value
                await client.send_message(
                    user_id,
                    f"⚠️ **Флуд контроль.** Ожидание {wait_time} секунд..."
                )
                await asyncio.sleep(wait_time)
                # Повторяем попытку
                i -= 1
                
            except Exception as e:
                await client.send_message(
                    user_id,
                    f"❌ **Ошибка при публикации истории {i}:**\n`{str(e)}`"
                )
                await asyncio.sleep(2)
        
        # Завершаем публикацию
        if current_story == total_stories:
            await client.send_message(
                user_id,
                f"✅ **Все истории успешно опубликованы!**\n\n"
                f"📊 Опубликовано: {total_stories} историй",
                reply_markup=get_main_keyboard()
            )
        
    except Exception as e:
        await client.send_message(
            user_id,
            f"❌ **Ошибка в процессе публикации:**\n`{str(e)}`",
            reply_markup=get_main_keyboard()
        )
    finally:
        if user_id in active_story_tasks:
            del active_story_tasks[user_id]
        
        # Завершаем сессию в БД
        db.complete_story(story_id, user_id)
        
        # Очищаем временные файлы
        if os.path.exists(media_path):
            os.remove(media_path)
        if os.path.exists(temp_data.get('mentions_file', '')):
            os.remove(temp_data['mentions_file'])
        
        db.clear_temp_data(user_id)

# Обработчик для кнопки остановки
@app.on_message(filters.text & filters.regex("^⏹️ Остановить публикацию$"))
async def stop_story_button(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id in active_story_tasks:
        active_story_tasks[user_id] = False
        del active_story_tasks[user_id]
        
        active_story = db.get_active_story(user_id)
        if active_story:
            db.complete_story(active_story['id'], user_id)
        
        await message.reply_text(
            "✅ **Публикация историй остановлена!**",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.reply_text(
            "❌ **У вас нет активной публикации историй.**",
            reply_markup=get_main_keyboard()
        )

# Функция Прогрев аккаунтов
@app.on_message(filters.text & filters.regex("^🔥 Прогрев аккаунтов$"))
async def warmup_start(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if len(accounts) < 2:
        await message.reply_text(
            "❌ **Для прогрева нужно минимум 2 аккаунта!**",
            reply_markup=get_functions_keyboard()
        )
        return
    
    # Проверяем, не запущен ли уже прогрев
    active_warmup = db.get_active_warmup_session(user_id)
    if active_warmup:
        await message.reply_text(
            "⚠️ **Прогрев уже запущен!**\n\n"
            "Отправьте /stop_warmup чтобы остановить.",
            reply_markup=get_main_keyboard()
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
        "step": "selecting_warmup_accounts",
        "accounts": temp_accounts
    })
    
    await message.reply_text(
        "🔥 **Прогрев аккаунтов**\n\n"
        "Выберите 2 аккаунта для прогрева:\n"
        "✅ - выбран, ⬜ - не выбран\n\n"
        "Нажимайте на кнопки с аккаунтами, чтобы выбрать.\n"
        "Когда выберете 2 аккаунта, нажмите '✅ Начать прогрев'",
        reply_markup=get_warmup_accounts_keyboard(temp_accounts)
    )

# Обработчик для кнопок выбора аккаунтов при прогреве
@app.on_message(filters.text & filters.regex(r"^[⬜✅] .* - .*$"))
async def handle_warmup_account_selection(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'selecting_warmup_accounts':
        return
    
    text = message.text
    if text.startswith('✅ ') or text.startswith('⬜ '):
        text = text[2:]
    
    # Ищем аккаунт
    for acc in temp_data['accounts']:
        if acc['name'] in text and acc['phone'] in text:
            # Проверяем, можно ли выбрать (макс 2)
            selected_count = len([a for a in temp_data['accounts'] if a['selected']])
            
            if not acc['selected'] and selected_count >= 2:
                await message.reply_text("❌ **Можно выбрать только 2 аккаунта!**")
                return
            
            acc['selected'] = not acc['selected']
            db.save_temp_data(user_id, temp_data)
            
            await message.reply_text(
                f"{'✅' if acc['selected'] else '⬜'} **Аккаунт {acc['name']}** {'выбран' if acc['selected'] else 'отменен'}",
                reply_markup=get_warmup_accounts_keyboard(temp_data['accounts'])
            )
            return

# Обработчик для кнопки "✅ Начать прогрев"
@app.on_message(filters.text & filters.regex("^✅ Начать прогрев$"))
async def start_warmup(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'selecting_warmup_accounts':
        return
    
    selected_accounts = [acc for acc in temp_data['accounts'] if acc['selected']]
    
    if len(selected_accounts) != 2:
        await message.reply_text("❌ **Выберите ровно 2 аккаунта!**")
        return
    
    await message.reply_text(
        "🔥 **Запускаю прогрев аккаунтов...**\n\n"
        "Аккаунты будут обмениваться сообщениями каждые 5 секунд.\n"
        "Отправьте /stop_warmup чтобы остановить.",
        reply_markup=get_main_keyboard()
    )
    
    await start_warmup_process(client, message, user_id, selected_accounts[0]['id'], selected_accounts[1]['id'])
    db.clear_temp_data(user_id)

# Обработчик для кнопки "⏹️ Остановить прогрев"
@app.on_message(filters.text & filters.regex("^⏹️ Остановить прогрев$"))
async def stop_warmup_button(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id in active_warmup_tasks:
        active_warmup_tasks[user_id] = False
        del active_warmup_tasks[user_id]
        
        warmup_session = db.get_active_warmup_session(user_id)
        if warmup_session:
            db.stop_warmup_session(warmup_session['id'], user_id)
        
        await message.reply_text(
            "✅ **Прогрев аккаунтов остановлен!**",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.reply_text(
            "❌ **У вас нет активного прогрева.**",
            reply_markup=get_main_keyboard()
        )

async def start_warmup_process(client: Client, message: Message, user_id: int, account1_id: int, account2_id: int):
    """Запускает процесс прогрева аккаунтов"""
    
    accounts = db.get_user_accounts(user_id)
    account1 = next((a for a in accounts if a['id'] == account1_id), None)
    account2 = next((a for a in accounts if a['id'] == account2_id), None)
    
    if not account1 or not account2:
        await client.send_message(user_id, "❌ **Аккаунты не найдены!**")
        return
    
    client1 = await get_user_client(user_id, account1)
    client2 = await get_user_client(user_id, account2)
    
    if not client1 or not client2:
        await client.send_message(user_id, "❌ **Не удалось подключиться к аккаунтам!**")
        return
    
    # Получаем информацию о пользователях
    me1 = await client1.get_me()
    me2 = await client2.get_me()
    
    # Создаем сессию в БД
    session_id = db.create_warmup_session(user_id, account1_id, account2_id)
    
    active_warmup_tasks[user_id] = True
    message_count = 0
    
    await client.send_message(
        user_id,
        f"🔥 **Прогрев запущен!**\n\n"
        f"👤 Аккаунт 1: {account1['account_name']}\n"
        f"👤 Аккаунт 2: {account2['account_name']}\n\n"
        f"📊 Отправлено сообщений: 0"
    )
    
    try:
        while active_warmup_tasks.get(user_id, False):
            # Отправляем сообщение от аккаунта 1 к аккаунту 2
            msg1 = random.choice(WARMUP_MESSAGES)
            await client1.send_message(me2.id, msg1)
            message_count += 1
            db.increment_messages_sent(user_id)
            db.update_warmup_session(session_id, message_count)
            
            await asyncio.sleep(5)
            
            if not active_warmup_tasks.get(user_id, False):
                break
            
            # Отправляем сообщение от аккаунта 2 к аккаунту 1
            msg2 = random.choice(WARMUP_MESSAGES)
            await client2.send_message(me1.id, msg2)
            message_count += 1
            db.increment_messages_sent(user_id)
            db.update_warmup_session(session_id, message_count)
            
            # Отправляем прогресс каждые 10 сообщений
            if message_count % 10 == 0:
                await client.send_message(
                    user_id,
                    f"📊 **Прогресс прогрева:**\n"
                    f"• Отправлено сообщений: {message_count}"
                )
            
            await asyncio.sleep(5)
            
    except Exception as e:
        await client.send_message(
            user_id,
            f"❌ **Ошибка в процессе прогрева:**\n`{str(e)}`"
        )
    finally:
        if user_id in active_warmup_tasks:
            del active_warmup_tasks[user_id]
        db.stop_warmup_session(session_id, user_id)
        
        await client.send_message(
            user_id,
            f"✅ **Прогрев завершен!**\n\n"
            f"📊 **Итог:**\n"
            f"• Отправлено сообщений: {message_count}"
        )

# Функция парсинга пользователей
@app.on_message(filters.text & filters.regex("^🔍 Парсинг пользователей$"))
async def parse_users_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ **Сначала выберите активный аккаунт!**",
            reply_markup=get_functions_keyboard()
        )
        return
    
    await message.reply_text(
        "🔍 **Парсинг пользователей**\n\n"
        "Отправьте ссылку на чат/канал для парсинга участников:\n\n"
        "Примеры:\n"
        "• `https://t.me/username`\n"
        "• `@username`\n"
        "• Ссылка на приглашение\n\n"
        "Бот соберет всех уникальных пользователей (без повторов).\n"
        "Отправьте /stopparse чтобы остановить.\n\n"
        "Или нажмите 'Отмена' для выхода.",
        reply_markup=get_cancel_keyboard()
    )
    
    db.save_temp_data(user_id, {
        "step": "waiting_chat_link",
        "account_id": active_account['id']
    })

# Функция умного парсинга
@app.on_message(filters.text & filters.regex("^🧠 Умный парсер$"))
async def smart_parse_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ **Сначала выберите активный аккаунт!**",
            reply_markup=get_functions_keyboard()
        )
        return
    
    await message.reply_text(
        "🧠 **Умный парсер**\n\n"
        "Этот инструмент поможет вам найти пользователей по ключевым словам.\n\n"
        "Отправьте запрос для поиска, например:\n"
        "• `маркетолог` - найдет пользователей с этим словом в bio\n"
        "• `https://t.me/username` - проанализирует участников чата\n"
        "• `@username` - найдет похожих пользователей\n\n"
        "Бот соберет данные и сохранит в CSV файл.\n"
        "Отправьте /stopparse чтобы остановить.\n\n"
        "Или нажмите 'Отмена' для выхода.",
        reply_markup=get_cancel_keyboard()
    )
    
    db.save_temp_data(user_id, {
        "step": "waiting_smart_query",
        "account_id": active_account['id']
    })

# Функция Анализатор чатов
@app.on_message(filters.text & filters.regex("^📊 Анализатор чатов$"))
async def chat_analyzer_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ **Сначала выберите активный аккаунт!**",
            reply_markup=get_functions_keyboard()
        )
        return
    
    # Сохраняем состояние
    db.save_temp_data(user_id, {
        "step": "analyzer_choice",
        "account_id": active_account['id']
    })
    
    await message.reply_text(
        "📊 **Анализатор чатов**\n\n"
        "Выберите тип анализа:\n\n"
        "• **Активность** - анализ активности участников\n"
        "• **Участники** - статистика по участникам\n"
        "• **Сообщения** - анализ сообщений и реакций\n\n"
        "Отправьте /stop_analyzer чтобы остановить процесс.",
        reply_markup=get_analyzer_choice_keyboard()
    )

@app.on_message(filters.text & filters.regex("^📊 Активность$"))
async def analyzer_activity(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'analyzer_choice':
        return
    
    await message.reply_text(
        "📊 **Анализ активности**\n\n"
        "Отправьте ссылку на чат/канал для анализа:\n\n"
        "Примеры:\n"
        "• `https://t.me/username`\n"
        "• `@username`\n\n"
        "Бот проанализирует активность за последние 1000 сообщений.\n\n"
        "Или нажмите 'Отмена' для выхода.",
        reply_markup=get_cancel_keyboard()
    )
    
    temp_data['step'] = 'waiting_analyzer_activity'
    temp_data['analyzer_type'] = 'activity'
    db.save_temp_data(user_id, temp_data)

@app.on_message(filters.text & filters.regex("^👥 Участники$"))
async def analyzer_members(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'analyzer_choice':
        return
    
    await message.reply_text(
        "👥 **Анализ участников**\n\n"
        "Отправьте ссылку на чат/канал для анализа:\n\n"
        "Примеры:\n"
        "• `https://t.me/username`\n"
        "• `@username`\n\n"
        "Бот соберет статистику по участникам.\n\n"
        "Или нажмите 'Отмена' для выхода.",
        reply_markup=get_cancel_keyboard()
    )
    
    temp_data['step'] = 'waiting_analyzer_members'
    temp_data['analyzer_type'] = 'members'
    db.save_temp_data(user_id, temp_data)

@app.on_message(filters.text & filters.regex("^📝 Сообщения$"))
async def analyzer_messages(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'analyzer_choice':
        return
    
    await message.reply_text(
        "📝 **Анализ сообщений**\n\n"
        "Отправьте ссылку на чат/канал для анализа:\n\n"
        "Примеры:\n"
        "• `https://t.me/username`\n"
        "• `@username`\n\n"
        "Бот проанализирует последние 1000 сообщений.\n\n"
        "Или нажмите 'Отмена' для выхода.",
        reply_markup=get_cancel_keyboard()
    )
    
    temp_data['step'] = 'waiting_analyzer_messages'
    temp_data['analyzer_type'] = 'messages'
    db.save_temp_data(user_id, temp_data)

# Функция Проверка спамблока
@app.on_message(filters.text & filters.regex("^🤖 Проверка спамблока$"))
async def spamblock_check_start(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if len(accounts) == 0:
        await message.reply_text(
            "❌ **У вас нет добавленных аккаунтов.**",
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
        "🤖 **Проверка спам-блока**\n\n"
        "Выберите аккаунты для проверки (можно несколько):\n"
        "✅ - выбран, ⬜ - не выбран\n\n"
        "Нажимайте на кнопки с аккаунтами, чтобы выбрать.\n"
        "Когда закончите, нажмите '✅ Начать проверку'",
        reply_markup=get_spamblock_accounts_keyboard(temp_accounts)
    )

# Обработчик для кнопок выбора аккаунтов при проверке спамблока
@app.on_message(filters.text & filters.regex(r"^[⬜✅] .* - .*$"))
async def handle_spamblock_account_selection(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'selecting_spamblock_accounts':
        return
    
    text = message.text
    if text.startswith('✅ ') or text.startswith('⬜ '):
        text = text[2:]
    
    for acc in temp_data['accounts']:
        if acc['name'] in text and acc['phone'] in text:
            acc['selected'] = not acc['selected']
            db.save_temp_data(user_id, temp_data)
            
            await message.reply_text(
                f"{'✅' if acc['selected'] else '⬜'} **Аккаунт {acc['name']}** {'выбран' if acc['selected'] else 'отменен'}",
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
        await message.reply_text("❌ **Выберите хотя бы один аккаунт!**")
        return
    
    if len(selected_accounts) > 10:
        await message.reply_text("❌ **Можно выбрать не больше 10 аккаунтов**")
        return
    
    await message.reply_text("🔄 **Начинаю проверку спам-блока...**", reply_markup=get_main_keyboard())
    
    await check_spamblock(client, message, user_id, selected_accounts)
    db.clear_temp_data(user_id)

async def check_spamblock(client: Client, message: Message, user_id: int, selected_accounts: list):
    """Проверка спамблока для выбранных аккаунтов"""
    
    results = []
    
    for acc_data in selected_accounts:
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
            spambot = await user_client.get_users("spambot")
            
            try:
                sent = await user_client.send_message(spambot.id, "/start")
                await asyncio.sleep(2)
                
                async for msg in user_client.get_chat_history(spambot.id, limit=1):
                    if msg.from_user and msg.from_user.is_self:
                        continue
                    await client.send_message(
                        user_id,
                        f"🤖 **{acc_data['name']}:**\n\n{msg.text}"
                    )
                    results.append(f"✅ {acc_data['name']}: статус получен")
                    break
                    
            except UserIsBlocked:
                await user_client.unblock_user(spambot.id)
                await asyncio.sleep(1)
                sent = await user_client.send_message(spambot.id, "/start")
                await asyncio.sleep(2)
                
                async for msg in user_client.get_chat_history(spambot.id, limit=1):
                    if msg.from_user and msg.from_user.is_self:
                        continue
                    await client.send_message(
                        user_id,
                        f"🤖 **{acc_data['name']} (после разблокировки):**\n\n{msg.text}"
                    )
                    results.append(f"✅ {acc_data['name']}: статус получен")
                    break
                    
        except Exception as e:
            results.append(f"❌ {acc_data['name']}: ошибка - {str(e)}")
    
    summary = "📊 **Результаты проверки спам-блока:**\n\n" + "\n".join(results)
    await client.send_message(user_id, summary)

# Функции для анализа чатов (продолжение)
async def analyze_chat(client: Client, message: Message, user_id: int, account_id: int, chat_link: str, analyzer_type: str):
    """Анализирует чат и выдает статистику"""
    
    active_account = db.get_active_account(user_id)
    if not active_account or active_account['id'] != account_id:
        await client.send_message(
            user_id,
            "❌ **Активный аккаунт изменился!**\nАнализ отменен."
        )
        return
    
    user_client = await get_user_client(user_id, active_account)
    if not user_client:
        await client.send_message(
            user_id,
            "❌ **Не удалось подключиться к аккаунту.**"
        )
        return
    
    try:
        # Получаем чат по ссылке
        if chat_link.startswith('https://t.me/'):
            username = chat_link.replace('https://t.me/', '').split('/')[0]
            chat = await user_client.get_chat(username)
        elif chat_link.startswith('@'):
            chat = await user_client.get_chat(chat_link)
        else:
            chat = await user_client.get_chat(chat_link)
        
        chat_id = chat.id
        chat_title = chat.title or chat_link
        
        await client.send_message(
            user_id,
            f"📊 **Анализ чата:** {chat_title}\n"
            f"Тип анализа: {analyzer_type}\n\n"
            f"🔄 Начинаю сбор данных..."
        )
        
        active_analyzer_tasks[user_id] = True
        
        if analyzer_type == 'activity':
            # Анализ активности
            await analyze_activity(client, user_client, user_id, chat_id, chat_title)
        elif analyzer_type == 'members':
            # Анализ участников
            await analyze_members(client, user_client, user_id, chat_id, chat_title)
        elif analyzer_type == 'messages':
            # Анализ сообщений
            await analyze_messages(client, user_client, user_id, chat_id, chat_title)
        
        db.increment_chats_analyzed(user_id)
        
    except Exception as e:
        await client.send_message(
            user_id,
            f"❌ **Ошибка при анализе:**\n`{str(e)}`"
        )
    
    if user_id in active_analyzer_tasks:
        del active_analyzer_tasks[user_id]

async def analyze_activity(client: Client, user_client: Client, user_id: int, chat_id: int, chat_title: str):
    """Анализирует активность в чате"""
    
    await client.send_message(
        user_id,
        f"📊 **Анализ активности в чате** {chat_title}\n\n"
        f"Собираю данные за последние 1000 сообщений..."
    )
    
    messages = []
    active_days = {}
    hours_distribution = {}
    
    async for msg in user_client.get_chat_history(chat_id, limit=1000):
        if not active_analyzer_tasks.get(user_id, False):
            await client.send_message(user_id, "⏹️ **Анализ остановлен пользователем.**")
            return
        
        if msg.date:
            messages.append(msg)
            
            # Анализ по дням
            day = msg.date.strftime('%Y-%m-%d')
            active_days[day] = active_days.get(day, 0) + 1
            
            # Анализ по часам
            hour = msg.date.hour
            hours_distribution[hour] = hours_distribution.get(hour, 0) + 1
    
    if not messages:
        await client.send_message(user_id, "❌ **Не найдено сообщений для анализа.**")
        return
    
    # Создаем отчет
    filename = f"activity_{chat_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = f"/tmp/{filename}"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"📊 ОТЧЕТ ПО АКТИВНОСТИ\n")
        f.write(f"Чат: {chat_title}\n")
        f.write(f"Проанализировано сообщений: {len(messages)}\n")
        f.write(f"Период: {min(messages, key=lambda x: x.date).date()} - {max(messages, key=lambda x: x.date).date()}\n\n")
        
        f.write("АКТИВНЫЕ ДНИ:\n")
        for day, count in sorted(active_days.items(), key=lambda x: x[1], reverse=True)[:10]:
            f.write(f"  {day}: {count} сообщений\n")
        
        f.write("\nРАСПРЕДЕЛЕНИЕ ПО ЧАСАМ:\n")
        for hour in range(24):
            count = hours_distribution.get(hour, 0)
            bar = "█" * (count // 10)
            f.write(f"  {hour:02d}:00 - {hour+1:02d}:00: {count} {bar}\n")
        
        f.write(f"\nПИК АКТИВНОСТИ: {max(hours_distribution, key=hours_distribution.get)}:00\n")
        f.write(f"СРЕДНЕЕ СООБЩЕНИЙ В ДЕНЬ: {len(messages)/len(active_days):.1f}\n")
    
    await client.send_document(
        user_id,
        document=filepath,
        caption=f"✅ **Анализ активности завершен!**\n\n"
                f"📊 Чат: {chat_title}\n"
                f"📝 Проанализировано: {len(messages)} сообщений"
    )
    
    os.remove(filepath)

async def analyze_members(client: Client, user_client: Client, user_id: int, chat_id: int, chat_title: str):
    """Анализирует участников чата"""
    
    await client.send_message(
        user_id,
        f"👥 **Анализ участников чата** {chat_title}\n\n"
        f"Собираю данные об участниках..."
    )
    
    members = []
    admin_count = 0
    bot_count = 0
    restricted_count = 0
    
    async for member in user_client.get_chat_members(chat_id):
        if not active_analyzer_tasks.get(user_id, False):
            await client.send_message(user_id, "⏹️ **Анализ остановлен пользователем.**")
            return
        
        members.append(member)
        
        if member.user.is_bot:
            bot_count += 1
        
        if member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
            admin_count += 1
        
        if member.user.is_scam or member.user.is_fake:
            restricted_count += 1
    
    # Создаем отчет
    filename = f"members_{chat_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = f"/tmp/{filename}"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"👥 ОТЧЕТ ПО УЧАСТНИКАМ\n")
        f.write(f"Чат: {chat_title}\n")
        f.write(f"Всего участников: {len(members)}\n\n")
        
        f.write(f"АДМИНИСТРАТОРЫ:\n")
        f.write(f"  Всего администраторов: {admin_count}\n")
        
        f.write(f"\nСТАТИСТИКА:\n")
        f.write(f"  Боты: {bot_count}\n")
        f.write(f"  Подозрительные: {restricted_count}\n")
        
        if len(members) > 0:
            with_username = sum(1 for m in members if m.user.username)
            f.write(f"  С username: {with_username} ({with_username/len(members)*100:.1f}%)\n")
        
        f.write(f"\nПОСЛЕДНИЕ УЧАСТНИКИ:\n")
        for member in sorted(members, key=lambda x: x.joined_date if x.joined_date else datetime.min, reverse=True)[:10]:
            joined = member.joined_date.strftime('%Y-%m-%d') if member.joined_date else 'Неизвестно'
            f.write(f"  {member.user.first_name} (@{member.user.username}) - {joined}\n")
    
    await client.send_document(
        user_id,
        document=filepath,
        caption=f"✅ **Анализ участников завершен!**\n\n"
                f"👥 Чат: {chat_title}\n"
                f"📊 Всего участников: {len(members)}"
    )
    
    os.remove(filepath)

async def analyze_messages(client: Client, user_client: Client, user_id: int, chat_id: int, chat_title: str):
    """Анализирует сообщения в чате"""
    
    await client.send_message(
        user_id,
        f"📝 **Анализ сообщений в чате** {chat_title}\n\n"
        f"Собираю данные за последние 1000 сообщений..."
    )
    
    messages = []
    top_users = Counter()
    reactions = Counter()
    words = Counter()
    
    async for msg in user_client.get_chat_history(chat_id, limit=1000):
        if not active_analyzer_tasks.get(user_id, False):
            await client.send_message(user_id, "⏹️ **Анализ остановлен пользователем.**")
            return
        
        messages.append(msg)
        
        if msg.from_user:
            user_name = msg.from_user.first_name or str(msg.from_user.id)
            top_users[user_name] += 1
        
        if msg.reactions:
            for reaction in msg.reactions.reactions:
                reactions[reaction.emoji] = reactions.get(reaction.emoji, 0) + reaction.count
        
        if msg.text:
            for word in msg.text.lower().split():
                if len(word) > 3:
                    words[word] += 1
    
    if not messages:
        await client.send_message(user_id, "❌ **Не найдено сообщений для анализа.**")
        return
    
    # Создаем отчет
    filename = f"messages_{chat_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = f"/tmp/{filename}"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"📝 ОТЧЕТ ПО СООБЩЕНИЯМ\n")
        f.write(f"Чат: {chat_title}\n")
        f.write(f"Проанализировано сообщений: {len(messages)}\n\n")
        
        f.write("ТОП-10 АКТИВНЫХ УЧАСТНИКОВ:\n")
        for user, count in top_users.most_common(10):
            f.write(f"  {user}: {count} сообщений\n")
        
        f.write("\nПОПУЛЯРНЫЕ РЕАКЦИИ:\n")
        for reaction, count in reactions.most_common(10):
            f.write(f"  {reaction}: {count} раз\n")
        
        f.write("\nТОП-10 ЧАСТО ИСПОЛЬЗУЕМЫХ СЛОВ:\n")
        for word, count in words.most_common(10):
            f.write(f"  {word}: {count} раз\n")
        
        f.write(f"\nСООБЩЕНИЙ С МЕДИА: {sum(1 for m in messages if m.media)}\n")
        f.write(f"СООБЩЕНИЙ СО ССЫЛКАМИ: {sum(1 for m in messages if m.text and 't.me' in m.text)}\n")
    
    await client.send_document(
        user_id,
        document=filepath,
        caption=f"✅ **Анализ сообщений завершен!**\n\n"
                f"📝 Чат: {chat_title}\n"
                f"📊 Проанализировано: {len(messages)} сообщений"
    )
    
    os.remove(filepath)

# Функция парсинга пользователей
async def parse_chat_users(client: Client, message: Message, user_id: int, account_id: int, chat_link: str):
    """Парсит пользователей из чата и сохраняет уникальных в файл"""
    
    active_account = db.get_active_account(user_id)
    if not active_account or active_account['id'] != account_id:
        await client.send_message(
            user_id,
            "❌ **Активный аккаунт изменился!**\nПарсинг отменен."
        )
        return
    
    user_client = await get_user_client(user_id, active_account)
    if not user_client:
        await client.send_message(
            user_id,
            "❌ **Не удалось подключиться к аккаунту.**"
        )
        return
    
    try:
        # Получаем чат по ссылке
        if chat_link.startswith('https://t.me/'):
            username = chat_link.replace('https://t.me/', '').split('/')[0]
            chat = await user_client.get_chat(username)
        elif chat_link.startswith('@'):
            chat = await user_client.get_chat(chat_link)
        else:
            # Пробуем как username
            chat = await user_client.get_chat(chat_link)
        
        chat_id = chat.id
        chat_title = chat.title or chat_link
        
        await client.send_message(
            user_id,
            f"📊 **Найден чат:** {chat_title}\n\n"
            f"🔄 Начинаю сбор участников (только уникальные)..."
        )
        
        # Очищаем старые данные
        db.clear_parsed_users(user_id, account_id)
        
        # Собираем уникальных участников
        users = []
        unique_ids = set()
        active_parse_tasks[user_id] = True
        count = 0
        
        # Сначала пробуем получить участников через get_chat_members
        try:
            async for member in user_client.get_chat_members(chat_id):
                if not active_parse_tasks.get(user_id, False):
                    await client.send_message(
                        user_id,
                        "⏹️ **Парсинг остановлен пользователем.**"
                    )
                    break
                
                if member.user and member.user.id not in unique_ids:
                    unique_ids.add(member.user.id)
                    user_info = {
                        'id': member.user.id,
                        'username': member.user.username or "",
                        'first_name': member.user.first_name or "",
                        'last_name': member.user.last_name or ""
                    }
                    users.append(user_info)
                    
                    if db.save_parsed_user(
                        user_id,
                        account_id,
                        str(chat_id),
                        chat_title,
                        member.user.id,
                        member.user.username or "",
                        member.user.first_name or "",
                        member.user.last_name or ""
                    ):
                        count += 1
                    
                    # Отправляем прогресс каждые 50 пользователей
                    if count % 50 == 0:
                        await client.send_message(
                            user_id,
                            f"📊 **Прогресс:** спарсено {count} уникальных пользователей..."
                        )
        except Exception as e:
            await client.send_message(
                user_id,
                f"⚠️ **Не удалось получить список участников:**\n`{str(e)}`\n\nПробую собрать через историю сообщений..."
            )
        
        # Если не удалось получить через get_chat_members, пробуем через историю сообщений
        if count == 0:
            await client.send_message(
                user_id,
                "🔄 **Сбор пользователей через историю сообщений...**"
            )
            
            async for msg in user_client.get_chat_history(chat_id, limit=1000):
                if not active_parse_tasks.get(user_id, False):
                    break
                
                if msg.from_user and msg.from_user.id not in unique_ids and not msg.from_user.is_self:
                    unique_ids.add(msg.from_user.id)
                    user_info = {
                        'id': msg.from_user.id,
                        'username': msg.from_user.username or "",
                        'first_name': msg.from_user.first_name or "",
                        'last_name': msg.from_user.last_name or ""
                    }
                    users.append(user_info)
                    
                    if db.save_parsed_user(
                        user_id,
                        account_id,
                        str(chat_id),
                        chat_title,
                        msg.from_user.id,
                        msg.from_user.username or "",
                        msg.from_user.first_name or "",
                        msg.from_user.last_name or ""
                    ):
                        count += 1
                    
                    if count % 50 == 0:
                        await client.send_message(
                            user_id,
                            f"📊 **Прогресс:** спарсено {count} уникальных пользователей..."
                        )
        
        if user_id in active_parse_tasks:
            del active_parse_tasks[user_id]
        
        if count > 0:
            # Создаем txt файл
            filename = f"users_{chat_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = f"/tmp/{filename}"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("ID | Username | Имя | Фамилия\n")
                f.write("-" * 50 + "\n")
                for user in sorted(users, key=lambda x: x['id']):
                    username = f"@{user['username']}" if user['username'] else "—"
                    f.write(f"{user['id']} | {username} | {user['first_name']} | {user['last_name']}\n")
            
            # Отправляем файл
            await client.send_document(
                user_id,
                document=filepath,
                caption=f"✅ **Парсинг завершен!**\n\n"
                        f"📊 **Статистика:**\n"
                        f"• Чат: {chat_title}\n"
                        f"• Уникальных пользователей: {count}\n"
                        f"• Формат: ID | Username | Имя | Фамилия\n"
                        f"• Повторы исключены"
            )
            
            # Обновляем статистику
            db.increment_users_parsed(user_id, count)
            
            # Удаляем временный файл
            os.remove(filepath)
        else:
            await client.send_message(
                user_id,
                "❌ **Не удалось найти пользователей.**\n\n"
                "Возможно, у вас нет доступа к чату или в чате нет сообщений."
            )
        
    except Exception as e:
        await client.send_message(
            user_id,
            f"❌ **Ошибка при парсинге:**\n`{str(e)}`"
        )
        
        if user_id in active_parse_tasks:
            del active_parse_tasks[user_id]

# Функция умного парсинга
async def smart_parse(client: Client, message: Message, user_id: int, account_id: int, query: str):
    """Умный парсер для поиска пользователей по ключевым словам"""
    
    active_account = db.get_active_account(user_id)
    if not active_account or active_account['id'] != account_id:
        await client.send_message(
            user_id,
            "❌ **Активный аккаунт изменился!**\nПарсинг отменен."
        )
        return
    
    user_client = await get_user_client(user_id, active_account)
    if not user_client:
        await client.send_message(
            user_id,
            "❌ **Не удалось подключиться к аккаунту.**"
        )
        return
    
    try:
        # Проверяем, является ли запрос ссылкой на чат
        if query.startswith('https://t.me/') or query.startswith('@'):
            # Парсим чат
            if query.startswith('https://t.me/'):
                username = query.replace('https://t.me/', '').split('/')[0]
                chat = await user_client.get_chat(username)
            else:
                chat = await user_client.get_chat(query)
            
            chat_id = chat.id
            chat_title = chat.title or query
            
            await client.send_message(
                user_id,
                f"🧠 **Умный парсинг чата:** {chat_title}\n\n"
                f"🔍 Анализирую участников..."
            )
            
            users = []
            unique_ids = set()
            active_parse_tasks[user_id] = True
            count = 0
            
            async for member in user_client.get_chat_members(chat_id):
                if not active_parse_tasks.get(user_id, False):
                    break
                
                if member.user and member.user.id not in unique_ids:
                    unique_ids.add(member.user.id)
                    user_info = {
                        'id': member.user.id,
                        'username': member.user.username or "",
                        'first_name': member.user.first_name or "",
                        'last_name': member.user.last_name or ""
                    }
                    users.append(user_info)
                    count += 1
                    
                    if count % 50 == 0:
                        await client.send_message(
                            user_id,
                            f"📊 **Прогресс:** обработано {count} пользователей..."
                        )
            
            if user_id in active_parse_tasks:
                del active_parse_tasks[user_id]
            
            if count > 0:
                # Создаем CSV файл
                filename = f"smart_{chat_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                filepath = f"/tmp/{filename}"
                
                with open(filepath, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['ID', 'Username', 'Имя', 'Фамилия'])
                    for user in users:
                        writer.writerow([user['id'], user['username'], user['first_name'], user['last_name']])
                
                await client.send_document(
                    user_id,
                    document=filepath,
                    caption=f"✅ **Умный парсинг завершен!**\n\n"
                            f"📊 **Статистика:**\n"
                            f"• Источник: {chat_title}\n"
                            f"• Найдено пользователей: {count}"
                )
                
                db.increment_smart_parsed(user_id, count)
                os.remove(filepath)
            else:
                await client.send_message(
                    user_id,
                    "❌ **Не удалось найти пользователей.**"
                )
        
        else:
            # Поиск по ключевому слову в bio
            await client.send_message(
                user_id,
                f"🧠 **Поиск пользователей по запросу:** {query}\n\n"
                f"🔍 Ищу в bio пользователей..."
            )
            
            # Здесь можно реализовать поиск по своим контактам или чатам
            # Для примера вернем сообщение о функциональности
            await client.send_message(
                user_id,
                f"🔍 **Функция в разработке**\n\n"
                f"Поиск по ключевому слову '{query}' будет доступен в следующем обновлении."
            )
            
    except Exception as e:
        await client.send_message(
            user_id,
            f"❌ **Ошибка при умном парсинге:**\n`{str(e)}`"
        )
        
        if user_id in active_parse_tasks:
            del active_parse_tasks[user_id]

# Функции рассылки
@app.on_message(filters.text & filters.regex("^📨 Рассылка$"))
async def mailing_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ **Сначала выберите активный аккаунт!**",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Проверяем, не запущена ли уже рассылка
    active_mailing = db.get_active_mailing(user_id)
    if active_mailing:
        await message.reply_text(
            "⚠️ **У вас уже есть активная рассылка!**\n\n"
            "Сначала дождитесь её завершения.",
            reply_markup=get_main_keyboard()
        )
        return
    
    status_msg = await message.reply_text(
        "🔄 **Загружаю список ваших чатов...**\n\n"
        "Это может занять некоторое время.",
        reply_markup=get_back_keyboard()
    )
    
    # Получаем клиент для аккаунта
    user_client = await get_user_client(user_id, active_account)
    if not user_client:
        await status_msg.edit_text(
            "❌ **Не удалось подключиться к аккаунту.**\n\n"
            "Попробуйте добавить его заново.",
            reply_markup=get_functions_keyboard()
        )
        return
    
    try:
        # Загружаем все диалоги (группы и каналы)
        all_chats = []
        async for dialog in user_client.get_dialogs():
            # Проверяем тип чата
            chat_type = dialog.chat.type
            if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                chat_info = {
                    'id': dialog.chat.id,
                    'title': dialog.chat.title or "Без названия",
                    'type': str(chat_type).split('.')[-1]
                }
                all_chats.append(chat_info)
        
        if not all_chats:
            await status_msg.edit_text(
                "❌ **У вас нет групп или каналов для рассылки.**",
                reply_markup=get_functions_keyboard()
            )
            return
        
        # Сохраняем чаты в БД (старые удалятся автоматически)
        db.save_chats(user_id, active_account['id'], all_chats)
        db.clear_selected_chats(user_id, active_account['id'])
        
        await status_msg.delete()
        
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
            f"❌ **Ошибка при загрузке чатов:**\n`{str(e)}`",
            reply_markup=get_functions_keyboard()
        )

async def show_chats_page(client: Client, message: Message, user_id: int, account_id: int, offset: int):
    """Показать страницу с чатами для выбора рассылки"""
    chats = db.get_chats(user_id, account_id, offset, CHATS_PER_PAGE)
    total_chats = db.get_total_chats_count(user_id, account_id)
    selected = db.get_selected_chats(user_id, account_id)
    
    if not chats:
        if offset == 0:
            await message.reply_text(
                "❌ **Чаты не найдены.**",
                reply_markup=get_functions_keyboard()
            )
        else:
            # Если чаты закончились, показываем выбранные
            await show_selected_chats_summary(client, message, user_id, account_id)
        return
    
    # Формируем сообщение со списком чатов
    text = f"📢 **Выберите чаты для рассылки** (макс. {MAX_CHATS_PER_MAILING})\n\n"
    text += f"📄 **Страница** {offset//CHATS_PER_PAGE + 1}/{(total_chats-1)//CHATS_PER_PAGE + 1}\n"
    text += f"📊 **Всего чатов:** {total_chats}\n"
    text += f"✅ **Выбрано:** {len(selected)}/{MAX_CHATS_PER_MAILING}\n\n"
    
    for i, chat in enumerate(chats, start=offset+1):
        status = "✅" if chat['selected'] else "⬜"
        text += f"{status} **{i}. {chat['chat_title']}**\n"
        text += f"   📁 Тип: `{chat['chat_type']}`\n\n"
    
    text += "\n📝 **Чтобы выбрать чат, отправьте его номер** (например: 1, 2, 3)\n"
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
            "❌ **Вы не выбрали ни одного чата.**",
            reply_markup=get_functions_keyboard()
        )
        return
    
    if len(selected) > MAX_CHATS_PER_MAILING:
        await message.reply_text(
            f"❌ **Выбрано слишком много чатов** ({len(selected)}).\n"
            f"Максимум: {MAX_CHATS_PER_MAILING}",
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
    
    mode_display = "📋 По очереди" if send_mode == 'sequential' else "🎲 Рандомно"
    auto_display = "✅ Вкл" if auto_subscribe else "❌ Выкл"
    
    text = (
        "⚙️ **Настройки рассылки**\n\n"
        f"📝 **Сообщений:** {len(messages)} шт.\n"
    )
    
    if messages:
        text += f"   Первое: `{messages[0][:50]}`...\n"
    
    text += (
        f"🔄 **Режим:** {mode_display}\n"
        f"⚡ **Автоподписка:** {auto_display}\n\n"
        f"Используйте кнопки ниже для настройки: 👇"
    )
    
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
        "📝 **Введите сообщения для рассылки**\n\n"
        "Отправляйте по одному сообщению.\n"
        f"Максимум: {MAX_CHATS_PER_MAILING} сообщений\n\n"
        "Когда закончите, отправьте **/done**",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("/done")], [KeyboardButton("❌ Отмена")]],
            resize_keyboard=True
        )
    )

@app.on_message(filters.text & filters.regex("^🔄 Режим: 📋 По очереди$|^🔄 Режим: 🎲 Рандомно$"))
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

@app.on_message(filters.text & filters.regex("^⚡ Автоподписка: ❌ Выкл$|^⚡ Автоподписка: ✅ Вкл$"))
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
        await message.reply_text("❌ **Сначала введите сообщения для рассылки!**")
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
        await message.reply_text("❌ **Активный аккаунт изменился!**\nНачните заново.")
        return
    
    # Запрашиваем количество сообщений на чат
    temp_data['step'] = 'waiting_message_count'
    db.save_temp_data(user_id, temp_data)
    
    await message.reply_text(
        "✏️ **Сколько сообщений отправить в каждый чат?**\n\n"
        f"(от 1 до {MAX_CHATS_PER_MAILING})",
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
    
    # Определяем тип выбора
    step = temp_data.get('step')
    
    if step == 'selecting_reaction_chats':
        # Для масс-реакций
        await show_reaction_chats_page(client, message, user_id, account_id, current_offset + CHATS_PER_PAGE)
    else:
        await show_chats_page(client, message, user_id, account_id, current_offset + CHATS_PER_PAGE)

@app.on_message(filters.text & filters.regex("^✅ Завершить выбор и продолжить$"))
async def finish_chat_selection(client: Client, message: Message):
    user_id = message.from_user.id
    temp_data = db.get_temp_data(user_id)
    account_id = temp_data.get('account_id')
    step = temp_data.get('step')
    
    if not account_id:
        await message.reply_text("❌ Ошибка. Начните заново.")
        return
    
    if step == 'selecting_reaction_chats':
        await show_selected_reaction_chats_summary(client, message, user_id, account_id)
    else:
        await show_selected_chats_summary(client, message, user_id, account_id)

# Функции масс-реакций
async def show_reaction_chats_page(client: Client, message: Message, user_id: int, account_id: int, offset: int):
    """Показать страницу с чатами для выбора реакций"""
    chats = db.get_chats(user_id, account_id, offset, CHATS_PER_PAGE)
    total_chats = db.get_total_chats_count(user_id, account_id)
    selected = db.get_selected_chats(user_id, account_id)
    max_chats = MAX_CHATS_PER_REACTION
    
    if not chats:
        if offset == 0:
            await message.reply_text(
                "❌ **Чаты не найдены.**",
                reply_markup=get_functions_keyboard()
            )
        else:
            # Если чаты закончились, показываем выбранные
            await show_selected_reaction_chats_summary(client, message, user_id, account_id)
        return
    
    # Формируем сообщение со списком чатов
    text = f"❤️ **Выберите чаты для масс-реакций** (макс. {max_chats})\n\n"
    text += f"📄 **Страница** {offset//CHATS_PER_PAGE + 1}/{(total_chats-1)//CHATS_PER_PAGE + 1}\n"
    text += f"📊 **Всего чатов:** {total_chats}\n"
    text += f"✅ **Выбрано:** {len(selected)}/{max_chats}\n\n"
    
    for i, chat in enumerate(chats, start=offset+1):
        status = "✅" if chat['selected'] else "⬜"
        text += f"{status} **{i}. {chat['chat_title']}**\n"
        text += f"   📁 Тип: `{chat['chat_type']}`\n\n"
    
    text += "\n📝 **Чтобы выбрать чат, отправьте его номер** (например: 1, 2, 3)\n"
    text += "Можно выбирать несколько чатов, отправляя номера по одному."
    
    # Сохраняем текущий offset в temp_data
    temp_data = db.get_temp_data(user_id)
    temp_data['offset'] = offset
    db.save_temp_data(user_id, temp_data)
    
    # Определяем, есть ли еще чаты
    has_more = (offset + CHATS_PER_PAGE) < total_chats
    
    await message.reply_text(
        text,
        reply_markup=get_chat_selection_keyboard(has_more, max_chats)
    )

async def show_selected_reaction_chats_summary(client: Client, message: Message, user_id: int, account_id: int):
    """Показать сводку выбранных чатов для реакций и запросить реакцию"""
    selected = db.get_selected_chats(user_id, account_id)
    
    if not selected:
        await message.reply_text(
            "❌ **Вы не выбрали ни одного чата.**",
            reply_markup=get_functions_keyboard()
        )
        return
    
    if len(selected) > MAX_CHATS_PER_REACTION:
        await message.reply_text(
            f"❌ **Выбрано слишком много чатов** ({len(selected)}).\n"
            f"Максимум: {MAX_CHATS_PER_REACTION}",
            reply_markup=get_functions_keyboard()
        )
        return
    
    # Сохраняем выбранные чаты
    temp_data = db.get_temp_data(user_id)
    temp_data['reaction_chats'] = selected
    temp_data['step'] = 'selecting_reaction'
    db.save_temp_data(user_id, temp_data)
    
    chat_list = "\n".join([f"• {chat['chat_title']}" for chat in selected])
    
    await message.reply_text(
        f"✅ **Выбрано чатов:** {len(selected)}\n\n"
        f"{chat_list}\n\n"
        f"❤️ **Выберите реакцию:**",
        reply_markup=get_reactions_keyboard()
    )

async def start_mass_reactions(client: Client, message: Message, user_id: int, temp_data: dict):
    """Запуск масс-реакций"""
    account_id = temp_data.get('account_id')
    chats = temp_data.get('reaction_chats', [])
    reaction = temp_data.get('reaction')
    
    if not all([account_id, chats, reaction]):
        await message.reply_text("❌ Ошибка данных. Начните заново.")
        return
    
    active_account = db.get_active_account(user_id)
    if not active_account or active_account['id'] != account_id:
        await message.reply_text("❌ **Активный аккаунт изменился!**\nНачните заново.")
        return
    
    user_client = await get_user_client(user_id, active_account)
    if not user_client:
        await message.reply_text("❌ Не удалось подключиться к аккаунту.")
        return
    
    reaction_id = db.create_active_reactions(user_id, account_id, chats, reaction)
    
    chat_list = "\n".join([f"• {chat['chat_title']}" for chat in chats])
    
    await message.reply_text(
        f"❤️ **Масс-реакции запущены!**\n\n"
        f"📊 **Отслеживается чатов:** {len(chats)}\n"
        f"❤️ **Реакция:** {reaction}\n\n"
        f"{chat_list}\n\n"
        f"⏳ Бот будет ставить реакцию на новые сообщения через 1 секунду.\n"
        f"📝 Отправьте /stop_reactions чтобы остановить.",
        reply_markup=get_main_keyboard()
    )
    
    active_reaction_tasks[user_id] = True
    
    for chat in chats:
        asyncio.create_task(
            monitor_chat_for_reactions(
                client, user_id, user_client, reaction_id,
                int(chat['chat_id']), chat['chat_title'], reaction
            )
        )
    
    db.clear_temp_data(user_id)

async def monitor_chat_for_reactions(client: Client, user_id: int, user_client: Client, 
                                     reaction_id: int, chat_id: int, chat_title: str, reaction: str):
    """Мониторит чат и ставит реакции на новые сообщения"""
    last_message_id = 0
    
    while active_reaction_tasks.get(user_id, False):
        try:
            async for message in user_client.get_chat_history(chat_id, limit=5):
                if message.from_user and message.from_user.is_self:
                    continue
                
                if message.id > last_message_id:
                    try:
                        await message.react(reaction)
                        db.increment_reactions_set(user_id)
                        
                        if message.id % 5 == 0:
                            await client.send_message(
                                user_id,
                                f"❤️ **Поставлена реакция** в чате {chat_title}\n"
                                f"На сообщение: {message.text[:50]}..."
                            )
                        
                        if message.id > last_message_id:
                            last_message_id = message.id
                            
                    except Exception as e:
                        print(f"Ошибка при установке реакции: {e}")
                
                break
            
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Ошибка в мониторинге чата {chat_title}: {e}")
            await asyncio.sleep(5)

# Функции создания каналов и групп
@app.on_message(filters.text & filters.regex("^📢 Создание каналов$"))
async def create_channel_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ **Сначала выберите активный аккаунт!**",
            reply_markup=get_functions_keyboard()
        )
        return
    
    # Сохраняем состояние
    db.save_temp_data(user_id, {
        "step": "creating_channel",
        "account_id": active_account['id'],
        "creation_type": "channel"
    })
    
    await message.reply_text(
        "📢 **Создание канала**\n\n"
        "Введите **название** для канала:\n\n"
        "Например: `Мой лучший канал`\n\n"
        "Или нажмите 'Отмена' для выхода.",
        reply_markup=get_cancel_keyboard()
    )

@app.on_message(filters.text & filters.regex("^👥 Создание групп$"))
async def create_group_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text(
            "❌ **Сначала выберите активный аккаунт!**",
            reply_markup=get_functions_keyboard()
        )
        return
    
    # Сохраняем состояние
    db.save_temp_data(user_id, {
        "step": "creating_group",
        "account_id": active_account['id'],
        "creation_type": "group"
    })
    
    await message.reply_text(
        "👥 **Создание группы**\n\n"
        "Введите **название** для группы:\n\n"
        "Например: `Моя лучшая группа`\n\n"
        "Или нажмите 'Отмена' для выхода.",
        reply_markup=get_cancel_keyboard()
    )

async def execute_creation(client: Client, message: Message, user_id: int, temp_data: dict):
    """Запуск создания каналов/групп"""
    account_id = temp_data.get('account_id')
    creation_type = temp_data.get('creation_type')
    title = temp_data.get('title')
    count = temp_data.get('count')
    archive = temp_data.get('archive', False)
    welcome = temp_data.get('welcome', False)
    welcome_text = temp_data.get('welcome_text', "")
    
    if not all([account_id, title, count]):
        await message.reply_text("❌ Ошибка данных. Начните заново.")
        return
    
    active_account = db.get_active_account(user_id)
    if not active_account or active_account['id'] != account_id:
        await message.reply_text("❌ Аккаунт изменился. Начните заново.")
        return
    
    user_client = await get_user_client(user_id, active_account)
    if not user_client:
        await message.reply_text("❌ Не удалось подключиться к аккаунту.")
        return
    
    type_name = "каналов" if creation_type == 'channel' else 'групп'
    
    await message.reply_text(
        f"🚀 **Начинаю создание {count} {type_name}...**\n\n"
        f"Это может занять некоторое время.",
        reply_markup=get_main_keyboard()
    )
    
    created = 0
    errors = 0
    
    for i in range(1, count + 1):
        try:
            current_title = f"{title} #{i}"
            
            if creation_type == 'channel':
                # Создаем канал
                chat = await user_client.create_channel(
                    title=current_title,
                    description=f"Создано через @VestSoftBot"
                )
                chat_type = 'channel'
                db.increment_channels_created(user_id)
            else:
                # Создаем группу (без добавления пользователей)
                chat = await user_client.create_group(
                    title=current_title,
                    users=[]  # Пустой список - никого не добавляем
                )
                chat_type = 'group'
                db.increment_groups_created(user_id)
            
            db.save_created_chat(
                user_id,
                account_id,
                str(chat.id),
                current_title,
                chat_type,
                chat.username or "",
                archive
            )
            
            if archive:
                try:
                    await user_client.archive_chats(chat.id)
                except:
                    pass
            
            if welcome and welcome_text:
                try:
                    await user_client.send_message(chat.id, welcome_text)
                except:
                    pass
            
            created += 1
            
            if created % 5 == 0 or created == count:
                await client.send_message(
                    user_id,
                    f"📊 **Прогресс:** {created}/{count}\n"
                    f"✅ Создано: {created}\n"
                    f"❌ Ошибок: {errors}"
                )
            
            await asyncio.sleep(2)
            
        except FloodWait as e:
            wait_time = e.value
            await client.send_message(
                user_id,
                f"⚠️ **Флуд контроль.** Ожидание {wait_time} секунд..."
            )
            await asyncio.sleep(wait_time)
            i -= 1
            
        except Exception as e:
            errors += 1
            await client.send_message(
                user_id,
                f"❌ **Ошибка при создании #{i}:**\n`{str(e)}`"
            )
            await asyncio.sleep(1)
    
    await client.send_message(
        user_id,
        f"✅ **Создание завершено!**\n\n"
        f"📊 **Результат:**\n"
        f"• ✅ Успешно: {created}\n"
        f"• ❌ Ошибок: {errors}\n"
        f"• 📦 В архиве: {'✅ Да' if archive else '❌ Нет'}\n"
        f"• 📝 Приветствие: {'✅ Да' if welcome else '❌ Нет'}",
        reply_markup=get_main_keyboard()
    )
    
    db.clear_temp_data(user_id)

# Callback обработчики для платежей
@app.on_callback_query()
async def handle_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data == "buy_subscription":
        text = (
            "💎 **Выберите тариф подписки**\n\n"
            "🔹 **1 день** — 3₽\n"
            "🔹 **7 дней** — 10₽\n"
            "🔹 **Навсегда** — 40₽\n\n"
            "✅ Оплата через Crypto Bot\n"
            "💬 Поддержка: @VestSoftSupport"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔹 1 день - 3₽", callback_data="plan_1day")],
            [InlineKeyboardButton("🔹 7 дней - 10₽", callback_data="plan_7days")],
            [InlineKeyboardButton("🔹 Навсегда - 40₽", callback_data="plan_forever")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_profile")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    
    elif data.startswith("plan_"):
        plan_type = data.replace("plan_", "")
        plan = SUBSCRIPTION_PLANS[plan_type]
        
        db.save_temp_data(user_id, {"selected_plan": plan_type})
        
        text = (
            f"💎 **Тариф:** {plan['name']}\n"
            f"💰 **Цена:** {plan['price_rub']}₽\n\n"
            f"💱 **Выберите валюту для оплаты:**\n\n"
            f"• USDT: 1 USDT = {EXCHANGE_RATES['USDT']}₽\n"
            f"• TON: 1 TON = {EXCHANGE_RATES['TON']}₽"
        )
        
        await callback_query.message.edit_text(text, reply_markup=get_payment_methods_keyboard())
    
    elif data == "pay_usdt" or data == "pay_ton":
        temp_data = db.get_temp_data(user_id)
        plan_type = temp_data.get("selected_plan")
        
        if not plan_type:
            await callback_query.answer("❌ Ошибка выбора тарифа")
            return
        
        plan = SUBSCRIPTION_PLANS[plan_type]
        currency = "USDT" if data == "pay_usdt" else "TON"
        
        invoice = await create_crypto_invoice(plan['price_rub'], currency, user_id, plan_type)
        
        if invoice:
            db.create_payment(
                user_id,
                invoice["invoice_id"],
                float(invoice["amount"]),
                currency,
                plan_type
            )
            
            text = (
                f"💳 **Счет на оплату создан!**\n\n"
                f"💰 **Сумма:** {invoice['amount']} {currency}\n"
                f"⏳ **Статус:** ожидает оплаты\n\n"
                f"🔗 **Ссылка для оплаты:**\n{invoice['pay_url']}"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_invoice_{invoice['invoice_id']}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="buy_subscription")]
            ])
            
            await callback_query.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback_query.message.edit_text(
                "❌ **Ошибка создания счета.**\nПопробуйте позже.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="buy_subscription")]])
            )
    
    elif data.startswith("check_invoice_"):
        invoice_id = data.replace("check_invoice_", "")
        
        status = await check_invoice_status(invoice_id)
        
        if status == "paid":
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, plan_type FROM payments WHERE invoice_id = ?", (invoice_id,))
                row = cursor.fetchone()
                
                if row:
                    payment_user_id, plan_type = row
                    
                    db.activate_subscription(payment_user_id, plan_type)
                    db.update_payment_status(invoice_id, "paid")
                    
                    await callback_query.message.edit_text(
                        "✅ **Оплата прошла успешно!**\n\nПодписка активирована.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👤 В профиль", callback_data="back_to_profile")]])
                    )
                else:
                    await callback_query.answer("❌ Платеж не найден")
        elif status == "active":
            await callback_query.answer("⏳ Счет еще ожидает оплаты")
        else:
            await callback_query.answer("❌ Не удалось проверить статус")
    
    elif data == "check_payment":
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
                (user_id,)
            )
            payments = cursor.fetchall()
        
        if not payments:
            await callback_query.answer("📭 У вас нет платежей")
            return
        
        text = "📊 **Ваши платежи:**\n\n"
        for p in payments:
            status_text = "✅ Оплачен" if p[6] == "paid" else "⏳ Ожидает"
            text += f"• {p[4]} ({p[3]} {p[4]}) — {status_text}\n"
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_profile")]])
        )
    
    elif data == "back_to_profile":
        accounts = db.get_user_accounts(user_id)
        active_account = db.get_active_account(user_id)
        has_subscription = db.check_subscription(user_id)
        user_data = db.get_user(user_id)
        max_accounts = db.get_max_accounts(user_id)
        created_chats = db.get_created_chats(user_id)
        
        channels = [c for c in created_chats if c['chat_type'] == 'channel']
        groups = [c for c in created_chats if c['chat_type'] == 'group']
        
        if has_subscription:
            if user_data["subscription_type"] == "forever":
                sub_status = "💎 **Навсегда**"
            elif user_data["subscription_end"]:
                end_date = datetime.fromisoformat(user_data["subscription_end"])
                days_left = (end_date - datetime.now()).days
                sub_status = f"✅ **Активна** (осталось {days_left} дн.)"
            else:
                sub_status = "✅ **Активна**"
        else:
            sub_status = "❌ **Бесплатная**"
        
        text = (
            "👤 **Ваш профиль**\n\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"📱 **Аккаунтов:** {len(accounts)}/{max_accounts}\n"
            f"💎 **Подписка:** {sub_status}\n"
            f"📨 **Сообщений отправлено:** {user_data['messages_sent']}\n"
            f"❤️ **Реакций поставлено:** {user_data['reactions_set']}\n"
            f"📱 **Историй опубликовано:** {user_data['stories_posted']}\n"
            f"🔍 **Пользователей спарсено:** {user_data['users_parsed']}\n"
            f"🧠 **Умный парсер:** {user_data['smart_parsed']}\n"
            f"📊 **Чатов проанализировано:** {user_data['chats_analyzed']}\n"
            f"📢 **Создано каналов:** {len(channels)}\n"
            f"👥 **Создано групп:** {len(groups)}\n"
            f"🔥 **Прогрев активен:** {'✅ Да' if user_data['warmup_active'] else '❌ Нет'}\n\n"
        )
        
        if active_account:
            username_info = f" (@{active_account['account_username']})" if active_account['account_username'] else ""
            text += (
                f"✅ **Активный аккаунт:**\n"
                f"• **{active_account['account_name']}**{username_info}\n"
                f"• 📱 `{active_account['phone_number']}`\n"
            )
        else:
            text += "❌ **Активный аккаунт не выбран**\n"
        
        text += "\n📢 **Наш канал:** @VestSoftTG"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 Купить подписку", callback_data="buy_subscription")],
            [InlineKeyboardButton("🔄 Проверить оплату", callback_data="check_payment")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)

# Функции для обработки текстовых сообщений в многошаговых сценариях
@app.on_message(filters.text & ~filters.regex("^(📱 Менеджер аккаунтов|⚙️ Функции|👤 Мой профиль|🛒 Купить аккаунт|➕ Добавить аккаунт|📋 Список аккаунтов|🔑 Выбрать активный аккаунт|❌ Удалить аккаунт|📂 Добавить из session файла|🔄 Обновить данные|◀️ Назад в главное меню|◀️ Назад|❌ Отмена|📨 Рассылка|📢 Создание каналов|👥 Создание групп|❤️ Масс-реакции|📱 Истории|🔥 Прогрев аккаунтов|🔍 Парсинг пользователей|🧠 Умный парсер|📊 Анализатор чатов|🤖 Проверка спамблока|📥 Загрузить ещё чаты|✅ Завершить выбор и продолжить|📝 Ввести сообщения|✅ Запустить рассылку|⏹️ Остановить публикацию|/done|/stop_reactions|/stop_warmup|/stopparse|/stop_analyzer|/stop_story|📊 Активность|👥 Участники|📝 Сообщения)$") & ~filters.regex("^🔄 Режим:.*$") & ~filters.regex("^⚡ Автоподписка:.*$") & ~filters.regex("^[⬜✅] .* - .*$") & ~filters.regex("^✅ Начать проверку$") & ~filters.regex("^✅ Начать прогрев$") & ~filters.regex("^⏹️ Остановить прогрев$") & ~filters.regex("^👍 Лайк|👎 Дизлайк|❤️ Сердечко|🔥 Огонь|🎉 Праздник$"))
async def handle_text_input(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.lower().strip()
    temp_data = db.get_temp_data(user_id)
    
    step = temp_data.get('step')
    
    if step in ["waiting_creation_count", "waiting_archive", "waiting_welcome", "waiting_welcome_text"]:
        # Обработка создания каналов/групп
        if step == "waiting_creation_count":
            if message.text.isdigit() and 1 <= int(message.text) <= 50:
                temp_data['count'] = int(message.text)
                temp_data['step'] = 'waiting_archive'
                db.save_temp_data(user_id, temp_data)
                
                await message.reply_text(
                    f"✅ **Будет создано:** {message.text}\n\n"
                    f"📦 **Отправлять в архив после создания?**\n"
                    f"Отправьте **да** или **нет**:"
                )
            else:
                await message.reply_text("❌ **Введите число от 1 до 50:**")
        
        elif step == "waiting_archive":
            if text in ["да", "нет"]:
                temp_data['archive'] = (text == "да")
                temp_data['step'] = 'waiting_welcome'
                db.save_temp_data(user_id, temp_data)
                
                await message.reply_text(
                    f"✅ **Архивация:** {'✅ Да' if temp_data['archive'] else '❌ Нет'}\n\n"
                    f"📝 **Отправлять приветственное сообщение?**\n"
                    f"Отправьте **да** или **нет**:"
                )
            else:
                await message.reply_text("❌ Пожалуйста, отправьте **да** или **нет**")
        
        elif step == "waiting_welcome":
            if text in ["да", "нет"]:
                temp_data['welcome'] = (text == "да")
                
                if temp_data['welcome']:
                    temp_data['step'] = 'waiting_welcome_text'
                    db.save_temp_data(user_id, temp_data)
                    
                    await message.reply_text(
                        "📝 **Введите текст приветственного сообщения:**",
                        reply_markup=get_cancel_keyboard()
                    )
                else:
                    # Запускаем создание
                    await execute_creation(client, message, user_id, temp_data)
            else:
                await message.reply_text("❌ Пожалуйста, отправьте **да** или **нет**")
        
        elif step == "waiting_welcome_text":
            temp_data['welcome_text'] = message.text
            db.save_temp_data(user_id, temp_data)
            
            # Запускаем создание
            await execute_creation(client, message, user_id, temp_data)
    
    elif step in ["waiting_chat_link", "waiting_smart_query", "waiting_analyzer_activity", "waiting_analyzer_members", "waiting_analyzer_messages"]:
        # Обработка парсинга и анализа
        if step == "waiting_chat_link":
            chat_link = message.text.strip()
            account_id = temp_data.get('account_id')
            
            await message.reply_text(
                "🔍 **Начинаю парсинг пользователей...**\n\n"
                "Это может занять некоторое время.\n"
                "Отправьте /stopparse чтобы остановить.\n"
                "Бот собирает только уникальных пользователей.",
                reply_markup=get_main_keyboard()
            )
            
            await parse_chat_users(client, message, user_id, account_id, chat_link)
            db.clear_temp_data(user_id)
        
        elif step == "waiting_smart_query":
            query = message.text.strip()
            account_id = temp_data.get('account_id')
            
            await message.reply_text(
                "🧠 **Начинаю умный парсинг...**\n\n"
                f"Запрос: {query}\n"
                "Это может занять некоторое время.\n"
                "Отправьте /stopparse чтобы остановить.",
                reply_markup=get_main_keyboard()
            )
            
            await smart_parse(client, message, user_id, account_id, query)
            db.clear_temp_data(user_id)
        
        elif step in ["waiting_analyzer_activity", "waiting_analyzer_members", "waiting_analyzer_messages"]:
            chat_link = message.text.strip()
            account_id = temp_data.get('account_id')
            analyzer_type = temp_data.get('analyzer_type')
            
            await message.reply_text(
                "📊 **Начинаю анализ чата...**\n\n"
                f"Тип анализа: {analyzer_type}\n"
                "Это может занять некоторое время.\n"
                "Отправьте /stop_analyzer чтобы остановить.",
                reply_markup=get_main_keyboard()
            )
            
            await analyze_chat(client, message, user_id, account_id, chat_link, analyzer_type)
            db.clear_temp_data(user_id)
    
    elif step in ["waiting_message_count", "waiting_delay"]:
        # Обработка рассылки
        if step == "waiting_message_count":
            if message.text.isdigit() and 1 <= int(message.text) <= MAX_CHATS_PER_MAILING:
                temp_data['message_count'] = int(message.text)
                temp_data['step'] = 'waiting_delay'
                db.save_temp_data(user_id, temp_data)
                
                await message.reply_text(
                    f"✅ **Будет отправлено {message.text} сообщений в каждый чат.**\n\n"
                    f"✏️ **Введите задержку между сообщениями** (в секундах, можно дробное число):"
                )
            else:
                await message.reply_text(f"❌ **Введите число от 1 до {MAX_CHATS_PER_MAILING}:**")
        
        elif step == "waiting_delay":
            try:
                delay = float(message.text)
                if delay < 0:
                    raise ValueError()
                
                temp_data['delay'] = delay
                db.save_temp_data(user_id, temp_data)
                
                await execute_mailing(client, message, user_id, temp_data)
                
            except ValueError:
                await message.reply_text("❌ **Введите корректное число** (например: 5 или 2.5):")

# Запуск бота
if __name__ == "__main__":
    print("🚀 Бот VEST SOFT запускается...")
    print(f"🤖 Bot API ID: {BOT_API_ID}")
    print(f"📢 Наш канал: @VestSoftTG")
    print("⏳ Ожидание подключения...")
    
    try:
        app.run()
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
