from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import AVAILABLE_REACTIONS, MAX_CHATS_PER_REACTION

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📱 Менеджер аккаунтов")],
            [KeyboardButton("⚙️ Функции")],
            [KeyboardButton("👤 Мой профиль")],
            [KeyboardButton("📢 Наш канал")]
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
            [KeyboardButton("🤖 Проверка спамблока")],
            [KeyboardButton("◀️ Назад в главное меню")]
        ],
        resize_keyboard=True
    )

def get_yes_no_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("✅ Да")],
            [KeyboardButton("❌ Нет")],
            [KeyboardButton("◀️ Назад")]
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

def get_payment_methods_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 USDT", callback_data="pay_usdt")],
        [InlineKeyboardButton("💎 TON", callback_data="pay_ton")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_profile")]
    ])
