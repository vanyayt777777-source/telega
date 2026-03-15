import os
import asyncio
import sqlite3
import json
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait, SessionPasswordNeeded, PhoneCodeInvalid, PhoneNumberInvalid, ApiIdInvalid
from pyrogram.errors import AccessTokenInvalid
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Конфигурация бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_API_ID = 32480523  # Ваш API ID
BOT_API_HASH = "147839735c9fa4e83451209e9b55cfc5"  # Ваш API Hash

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

MAX_ACCOUNTS = 3
MAX_CHATS_PER_MAILING = 5
CHATS_PER_PAGE = 10
DATABASE_PATH = "vest_soft.db"

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
            [KeyboardButton("◀️ Назад в главное меню")]
        ],
        resize_keyboard=True
    )

def get_functions_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📨 Рассылка")],
            [KeyboardButton("◀️ Назад в главное меню")]
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
                    mailing_status TEXT DEFAULT 'idle',
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
                    selected BOOLEAN DEFAULT 0,
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
                    "mailing_status": row[2],
                    "created_at": row[3]
                }
            return None
    
    def create_user(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
                (user_id,)
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
                    "created_at": row[6]
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
                    "created_at": row[6]
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
            # Добавляем новые чаты
            for chat in chats:
                cursor.execute(
                    """INSERT OR IGNORE INTO chats (user_id, account_id, chat_id, chat_title) 
                       VALUES (?, ?, ?, ?)""",
                    (user_id, account_id, str(chat['id']), chat['title'])
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
                    "selected": bool(row[5])
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
                    "chat_title": row[4]
                })
            return chats

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
        api_id=BOT_API_ID,  # Используем API бота
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

@app.on_message(filters.text & filters.regex("^📱 Менеджер аккаунтов$"))
async def account_manager_menu(client: Client, message: Message):
    await message.reply_text(
        "📱 *Менеджер аккаунтов*\n\n"
        "Выберите действие:",
        reply_markup=get_account_manager_keyboard()
    )

@app.on_message(filters.text & filters.regex("^📋 Список аккаунтов$"))
async def list_accounts(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await message.reply_text(
            "📋 У вас пока нет добавленных аккаунтов.",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    text = "📋 *Список ваших аккаунтов:*\n\n"
    for acc in accounts:
        status = "✅ АКТИВЕН" if acc['is_active'] else "❌ не активен"
        text += f"• {acc['account_name']}: {acc['phone_number']} - {status}\n"
    
    text += f"\nВсего аккаунтов: {len(accounts)}/{MAX_ACCOUNTS}"
    
    await message.reply_text(
        text,
        reply_markup=get_account_manager_keyboard()
    )

@app.on_message(filters.text & filters.regex("^➕ Добавить аккаунт$"))
async def add_account_start(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if len(accounts) >= MAX_ACCOUNTS:
        await message.reply_text(
            f"❌ Вы достигли лимита в {MAX_ACCOUNTS} аккаунтов.\n"
            "Удалите один из существующих аккаунтов, чтобы добавить новый.",
            reply_markup=get_account_manager_keyboard()
        )
        return
    
    db.save_temp_data(user_id, {"step": "waiting_phone"})
    
    await message.reply_text(
        "📱 Для добавления аккаунта введите номер телефона\n"
        "в международном формате (например: +79001234567):",
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
    
    text = "🔑 *Выберите активный аккаунт:*\n\n"
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
        f"⚙️ *Функции*\n\n"
        f"Активный аккаунт: {active_account['account_name']} ({active_account['phone_number']})\n\n"
        f"Выберите функцию:",
        reply_markup=get_functions_keyboard()
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
    
    await message.reply_text(
        "🔄 Загружаю список ваших чатов... Это может занять некоторое время.",
        reply_markup=get_back_keyboard()
    )
    
    # Получаем клиент для аккаунта
    user_client = await get_user_client(user_id, active_account)
    if not user_client:
        await message.reply_text(
            "❌ Не удалось подключиться к аккаунту. Попробуйте добавить его заново.",
            reply_markup=get_functions_keyboard()
        )
        return
    
    try:
        # Загружаем все диалоги (группы и каналы)
        all_chats = []
        async for dialog in user_client.get_dialogs():
            if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                all_chats.append({
                    'id': dialog.chat.id,
                    'title': dialog.chat.title or "Без названия"
                })
        
        if not all_chats:
            await message.reply_text(
                "❌ У вас нет групп или каналов для рассылки.",
                reply_markup=get_functions_keyboard()
            )
            return
        
        # Сохраняем все чаты в БД
        db.save_chats(user_id, active_account['id'], all_chats)
        db.clear_selected_chats(user_id, active_account['id'])
        
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
        await message.reply_text(
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
    text = f"📢 *Выберите чаты для рассылки (макс. {MAX_CHATS_PER_MAILING})*\n\n"
    text += f"Страница {offset//CHATS_PER_PAGE + 1}/{(total_chats-1)//CHATS_PER_PAGE + 1}\n"
    text += f"Всего чатов: {total_chats}\n"
    text += f"Выбрано: {len(selected)}/{MAX_CHATS_PER_MAILING}\n\n"
    
    for i, chat in enumerate(chats, start=offset+1):
        status = "✅" if chat['selected'] else "⬜"
        text += f"{status} {i}. {chat['chat_title']}\n"
        text += f"   ID: `{chat['chat_id']}`\n\n"
    
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
    """Показать сводку выбранных чатов и запросить сообщение"""
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
    
    # Сохраняем состояние для следующего шага
    db.save_temp_data(user_id, {
        "step": "waiting_message",
        "account_id": account_id,
        "chats": selected
    })
    
    chat_list = "\n".join([f"• {chat['chat_title']}" for chat in selected])
    
    await message.reply_text(
        f"✅ *Выбрано чатов: {len(selected)}*\n\n"
        f"{chat_list}\n\n"
        f"✏️ Теперь отправьте текст сообщения для рассылки:",
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
    
    text = "👤 *Ваш профиль*\n\n"
    text += f"Telegram ID: `{user_id}`\n"
    text += f"Аккаунтов добавлено: {len(accounts)}/{MAX_ACCOUNTS}\n"
    
    if active_account:
        text += f"\n✅ *Активный аккаунт:*\n"
        text += f"• {active_account['account_name']}\n"
        text += f"• {active_account['phone_number']}"
    else:
        text += "\n❌ Активный аккаунт не выбран"
    
    await message.reply_text(
        text,
        reply_markup=get_main_keyboard()
    )

@app.on_message(filters.text & filters.regex("^◀️ Назад в главное меню$|^◀️ Назад$"))
async def back_to_main(client: Client, message: Message):
    user_id = message.from_user.id
    db.clear_temp_data(user_id)
    await message.reply_text(
        "Главное меню:",
        reply_markup=get_main_keyboard()
    )

@app.on_message(filters.text & filters.regex("^❌ Отмена$"))
async def cancel_action(client: Client, message: Message):
    user_id = message.from_user.id
    db.clear_temp_data(user_id)
    await message.reply_text(
        "Действие отменено.",
        reply_markup=get_main_keyboard()
    )

# Обработчик текстовых сообщений (для многошаговых сценариев)
@app.on_message(filters.text & ~filters.regex("^(📱 Менеджер аккаунтов|⚙️ Функции|👤 Профиль|➕ Добавить аккаунт|📋 Список аккаунтов|🔑 Выбрать активный аккаунт|◀️ Назад в главное меню|◀️ Назад|❌ Отмена|📨 Рассылка|📥 Загрузить ещё чаты|✅ Завершить выбор и продолжить)$"))
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
    
    elif step == "waiting_message":
        temp_data['message_text'] = text
        temp_data['step'] = "waiting_count"
        db.save_temp_data(user_id, temp_data)
        
        await message.reply_text(
            "✅ Текст сообщения сохранен.\n\n"
            "✏️ Сколько сообщений отправить в каждый чат? (введите число):"
        )
    
    elif step == "waiting_count":
        if not text.isdigit() or int(text) <= 0:
            await message.reply_text("❌ Введите положительное число:")
            return
        
        temp_data['message_count'] = int(text)
        temp_data['step'] = "waiting_delay"
        db.save_temp_data(user_id, temp_data)
        
        await message.reply_text(
            f"✅ Будет отправлено {text} сообщений в каждый чат.\n\n"
            f"✏️ Введите задержку между сообщениями (в секундах, можно дробное число):"
        )
    
    elif step == "waiting_delay":
        try:
            delay = float(text)
            if delay < 0:
                raise ValueError()
            
            temp_data['delay'] = delay
            db.save_temp_data(user_id, temp_data)
            
            # Запускаем рассылку
            await start_mailing(client, message, user_id, temp_data)
            
        except ValueError:
            await message.reply_text(
                "❌ Введите корректное число (например: 5 или 2.5):"
            )

async def start_mailing(client: Client, message: Message, user_id: int, temp_data: dict):
    """Запуск рассылки"""
    account_id = temp_data.get('account_id')
    message_text = temp_data.get('message_text')
    message_count = temp_data.get('message_count')
    delay = temp_data.get('delay')
    chats = temp_data.get('chats', [])
    
    if not all([account_id, message_text, message_count, delay, chats]):
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
    
    await message.reply_text(
        "🚀 *Запускаю рассылку...*\n\n"
        f"Чатов: {len(chats)}\n"
        f"Сообщений в чат: {message_count}\n"
        f"Задержка: {delay} сек\n\n"
        "Я буду сообщать о прогрессе.",
        reply_markup=get_main_keyboard()
    )
    
    # Запускаем рассылку
    total_messages = len(chats) * message_count
    sent_messages = 0
    
    for chat in chats:
        chat_title = chat['chat_title']
        chat_id = int(chat['chat_id'])
        
        for msg_num in range(1, message_count + 1):
            try:
                await user_client.send_message(chat_id, message_text)
                sent_messages += 1
                
                # Отправляем прогресс каждые 5 сообщений
                if sent_messages % 5 == 0 or sent_messages == total_messages:
                    await client.send_message(
                        user_id,
                        f"📊 Прогресс: {sent_messages}/{total_messages}\n"
                        f"Текущий чат: {chat_title} ({msg_num}/{message_count})"
                    )
                
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
                await user_client.send_message(chat_id, message_text)
                sent_messages += 1
                
            except Exception as e:
                await client.send_message(
                    user_id,
                    f"❌ Ошибка в чате {chat_title}: {str(e)}"
                )
            
            # Небольшая задержка после ошибок тоже
            await asyncio.sleep(1)
        
        # Небольшая задержка между чатами
        await asyncio.sleep(2)
    
    await client.send_message(
        user_id,
        f"✅ *Рассылка завершена!*\n\n"
        f"Отправлено сообщений: {sent_messages}/{total_messages}",
        reply_markup=get_main_keyboard()
    )
    
    db.clear_temp_data(user_id)

# Запуск бота
if __name__ == "__main__":
    print("🚀 Бот VEST SOFT запускается...")
    print(f"Бот API ID: {BOT_API_ID}")
    print(f"Токен бота загружен из переменных окружения")
    print("Ожидание подключения...")
    
    try:
        app.run()
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
