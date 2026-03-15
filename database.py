import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from config import DATABASE_PATH, MAX_ACCOUNTS_FREE, MAX_ACCOUNTS_PAID, SUBSCRIPTION_PLANS, CHATS_PER_PAGE

class Database:
    def __init__(self):
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(DATABASE_PATH)
    
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    active_account_id INTEGER,
                    subscription_type TEXT DEFAULT 'free',
                    subscription_end TIMESTAMP,
                    mailing_status TEXT DEFAULT 'idle',
                    auto_subscribe_enabled BOOLEAN DEFAULT 0,
                    channels_created INTEGER DEFAULT 0,
                    groups_created INTEGER DEFAULT 0,
                    messages_sent INTEGER DEFAULT 0,
                    reactions_set INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
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
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS temp_data (
                    user_id INTEGER PRIMARY KEY,
                    data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
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
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mailing_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
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
                    "channels_created": row[6],
                    "groups_created": row[7],
                    "messages_sent": row[8],
                    "reactions_set": row[9],
                    "created_at": row[10]
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
        if self.check_subscription(user_id):
            return MAX_ACCOUNTS_PAID
        return MAX_ACCOUNTS_FREE
    
    def activate_subscription(self, user_id: int, plan_type: str):
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
            cursor.execute(
                "UPDATE accounts SET is_active = 0 WHERE user_id = ?",
                (user_id,)
            )
            cursor.execute(
                "UPDATE accounts SET is_active = 1 WHERE id = ? AND user_id = ?",
                (account_id, user_id)
            )
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
            cursor.execute(
                "DELETE FROM chats WHERE user_id = ? AND account_id = ?",
                (user_id, account_id)
            )
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
            cursor.execute("DELETE FROM mailing_messages WHERE user_id = ?", (user_id,))
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
            cursor.execute(
                "UPDATE users SET mailing_status = 'idle' WHERE user_id = (SELECT user_id FROM active_mailings WHERE id = ?)",
                (mailing_id,)
            )
            conn.commit()
    
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
