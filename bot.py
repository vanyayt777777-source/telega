import os
import asyncio
import random
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait, SessionPasswordNeeded, PhoneCodeInvalid, PhoneNumberInvalid
from pyrogram.errors import PeerIdInvalid

from config import *
from database import Database
from keyboards import *
from utils import get_user_client, stop_user_client, active_reaction_tasks
from channel_group import execute_creation
from mass_reactions import start_mass_reactions
from spamblock import check_spamblock
from profile_payments import *

# Инициализация бота
app = Client(
    "vest_soft_bot",
    api_id=BOT_API_ID,
    api_hash=BOT_API_HASH,
    bot_token=BOT_TOKEN
)

db = Database()

# Импортируем все функции в глобальную область видимости для обработчиков
# (это нужно сделать после определения всех функций)

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
        "✓ Проверка спам-блока\n"
        "✓ Автоподписка\n\n"
        "📢 **Наш канал:** @VestSoftTG\n"
        "💬 **Поддержка:** @VestSoftSupport\n\n"
        "Используйте кнопки меню для навигации. 👇"
    )
    
    await message.reply_text(welcome_text, reply_markup=get_main_keyboard())

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
    
    temp_data['step'] = 'mailing_settings'
    temp_data['messages'] = messages
    del temp_data['temp_messages']
    db.save_temp_data(user_id, temp_data)
    
    db.save_mailing_messages(user_id, messages)
    
    await message.reply_text(f"✅ Сохранено {len(messages)} сообщений.")
    await show_mailing_settings(client, message, user_id)

@app.on_message(filters.command("stop_reactions"))
async def stop_reactions_command(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id in active_reaction_tasks:
        active_reaction_tasks[user_id] = False
        del active_reaction_tasks[user_id]
        
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

# Обработчики навигации
@app.on_message(filters.text & filters.regex("^📱 Менеджер аккаунтов$"))
async def account_manager_menu(client: Client, message: Message):
    text = (
        "📱 **Менеджер аккаунтов**\n\n"
        "Здесь вы можете управлять своими Telegram аккаунтами:\n"
        "• Добавлять новые аккаунты\n"
        "• Просматривать список\n"
        "• Выбирать активный аккаунт\n"
        "• Удалять ненужные\n"
        "• Обновлять данные\n\n"
        "Выберите действие: 👇"
    )
    
    await message.reply_text(text, reply_markup=get_account_manager_keyboard())

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
        f"📢 **Создано каналов:** {len(channels)}\n"
        f"👥 **Создано групп:** {len(groups)}\n"
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
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Купить подписку", callback_data="buy_subscription")],
        [InlineKeyboardButton("🔄 Проверить оплату", callback_data="check_payment")]
    ])
    
    await message.reply_text(text, reply_markup=keyboard)

@app.on_message(filters.text & filters.regex("^📢 Наш канал$"))
async def our_channel(client: Client, message: Message):
    text = (
        "📢 **Наш канал:** @VestSoftTG\n\n"
        "🔥 **Подпишитесь, чтобы быть в курсе новостей!**\n\n"
        "Там вы найдете:\n"
        "• Новые функции бота\n"
        "• Обновления и улучшения\n"
        "• Промокоды и скидки\n"
        "• Полезные советы\n\n"
        "👉 [Перейти в канал](https://t.me/VestSoftTG)"
    )
    
    await message.reply_text(text, disable_web_page_preview=True, reply_markup=get_main_keyboard())

@app.on_message(filters.text & filters.regex("^◀️ Назад в главное меню$|^◀️ Назад$"))
async def back_to_main(client: Client, message: Message):
    user_id = message.from_user.id
    db.clear_temp_data(user_id)
    await message.reply_text("🏠 **Главное меню:**", reply_markup=get_main_keyboard())

@app.on_message(filters.text & filters.regex("^❌ Отмена$"))
async def cancel_action(client: Client, message: Message):
    user_id = message.from_user.id
    db.clear_temp_data(user_id)
    await message.reply_text("❌ **Действие отменено.**", reply_markup=get_main_keyboard())

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
        
        text += f"• **{acc['account_name']}**{username_info}\n"
        text += f"  📱 `{acc['phone_number']}`\n"
        text += f"  {status}{block_status}\n"
        text += f"  🆔 ID: `{acc['id']}`\n\n"
    
    text += f"📊 **Всего аккаунтов:** {len(accounts)}/{max_accounts}"
    
    await message.reply_text(text, reply_markup=get_account_manager_keyboard())

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

@app.on_message(filters.text & filters.regex("^❌ Удалить аккаунт$"))
async def delete_account_menu(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await message.reply_text("❌ **У вас нет добавленных аккаунтов.**", reply_markup=get_account_manager_keyboard())
        return
    
    db.save_temp_data(user_id, {"step": "deleting_account", "accounts": accounts})
    
    text = "❌ **Выберите аккаунт для удаления:**\n\n"
    for i, acc in enumerate(accounts, 1):
        text += f"{i}. **{acc['account_name']}** - `{acc['phone_number']}`\n"
    text += "\n📝 **Отправьте номер аккаунта** (1, 2, 3...) или нажмите Отмена"
    
    await message.reply_text(text, reply_markup=get_cancel_keyboard())

@app.on_message(filters.text & filters.regex("^🔄 Обновить данные$"))
async def refresh_account_data(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await message.reply_text("❌ **У вас нет добавленных аккаунтов.**", reply_markup=get_account_manager_keyboard())
        return
    
    await message.reply_text(
        "🔄 **Обновляю данные аккаунтов...**\n\nЭто может занять некоторое время.",
        reply_markup=get_back_keyboard()
    )
    
    updated = 0
    for account in accounts:
        user_client = await get_user_client(user_id, account, db)
        if user_client:
            try:
                me = await user_client.get_me()
                if me.username != account.get('account_username'):
                    db.update_account_username(account['id'], me.username or "")
                    updated += 1
            except:
                pass
    
    await message.reply_text(
        f"✅ **Обновление завершено!**\n\nОбновлено аккаунтов: {updated}",
        reply_markup=get_account_manager_keyboard()
    )

@app.on_message(filters.text & filters.regex("^🔑 Выбрать активный аккаунт$"))
async def select_active_account_menu(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if not accounts:
        await message.reply_text("❌ **У вас нет добавленных аккаунтов.**", reply_markup=get_account_manager_keyboard())
        return
    
    db.save_temp_data(user_id, {"step": "selecting_account", "accounts": accounts})
    
    text = "🔑 **Выберите активный аккаунт:**\n\n"
    for i, acc in enumerate(accounts, 1):
        status = " ✅ **(текущий)**" if acc['is_active'] else ""
        text += f"{i}. **{acc['account_name']}** - `{acc['phone_number']}`{status}\n"
    text += "\n📝 **Отправьте номер аккаунта** (1, 2, 3...) или нажмите Отмена"
    
    await message.reply_text(text, reply_markup=get_cancel_keyboard())

# Создание каналов/групп
@app.on_message(filters.text & filters.regex("^📢 Создание каналов$"))
async def create_channel_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text("❌ **Сначала выберите активный аккаунт!**", reply_markup=get_functions_keyboard())
        return
    
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
        await message.reply_text("❌ **Сначала выберите активный аккаунт!**", reply_markup=get_functions_keyboard())
        return
    
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

# Масс-реакции
@app.on_message(filters.text & filters.regex("^❤️ Масс-реакции$"))
async def mass_reactions_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text("❌ **Сначала выберите активный аккаунт!**", reply_markup=get_functions_keyboard())
        return
    
    active_reactions = db.get_active_reactions(user_id)
    if active_reactions:
        await message.reply_text(
            "⚠️ **У вас уже есть активные масс-реакции!**\n\n"
            f"Отслеживается {len(active_reactions['chats'])} чатов.\n"
            f"Реакция: {active_reactions['reaction']}\n\n"
            f"Отправьте /stop_reactions чтобы остановить.",
            reply_markup=get_main_keyboard()
        )
        return
    
    status_msg = await message.reply_text(
        "🔄 **Загружаю список ваших чатов...**\n\nЭто может занять некоторое время.",
        reply_markup=get_back_keyboard()
    )
    
    user_client = await get_user_client(user_id, active_account, db)
    if not user_client:
        await status_msg.edit_text(
            "❌ **Не удалось подключиться к аккаунту.**\n\nПопробуйте добавить его заново.",
            reply_markup=get_functions_keyboard()
        )
        return
    
    try:
        all_chats = []
        async for dialog in user_client.get_dialogs():
            if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                all_chats.append({
                    'id': dialog.chat.id,
                    'title': dialog.chat.title or "Без названия",
                    'type': str(dialog.chat.type).split('.')[-1]
                })
        
        if not all_chats:
            await status_msg.edit_text(
                "❌ **У вас нет групп или каналов для отслеживания.**",
                reply_markup=get_functions_keyboard()
            )
            return
        
        db.save_chats(user_id, active_account['id'], all_chats)
        db.clear_selected_chats(user_id, active_account['id'])
        
        await status_msg.delete()
        
        db.save_temp_data(user_id, {
            "step": "selecting_reaction_chats",
            "account_id": active_account['id'],
            "offset": 0,
            "selected_chats": [],
            "max_chats": MAX_CHATS_PER_REACTION
        })
        
        await show_reaction_chats_page(client, message, user_id, active_account['id'], 0)
        
    except Exception as e:
        await status_msg.edit_text(
            f"❌ **Ошибка при загрузке чатов:**\n`{str(e)}`",
            reply_markup=get_functions_keyboard()
        )

async def show_reaction_chats_page(client, message, user_id, account_id, offset):
    chats = db.get_chats(user_id, account_id, offset, CHATS_PER_PAGE)
    total_chats = db.get_total_chats_count(user_id, account_id)
    selected = db.get_selected_chats(user_id, account_id)
    
    if not chats:
        if offset == 0:
            await message.reply_text("❌ **Чаты не найдены.**", reply_markup=get_functions_keyboard())
        else:
            await show_selected_reaction_chats_summary(client, message, user_id, account_id)
        return
    
    text = f"❤️ **Выберите чаты для масс-реакций** (макс. {MAX_CHATS_PER_REACTION})\n\n"
    text += f"📄 **Страница** {offset//CHATS_PER_PAGE + 1}/{(total_chats-1)//CHATS_PER_PAGE + 1}\n"
    text += f"📊 **Всего чатов:** {total_chats}\n"
    text += f"✅ **Выбрано:** {len(selected)}/{MAX_CHATS_PER_REACTION}\n\n"
    
    for i, chat in enumerate(chats, start=offset+1):
        status = "✅" if chat['selected'] else "⬜"
        text += f"{status} **{i}. {chat['chat_title']}**\n"
        text += f"   📁 Тип: `{chat['chat_type']}`\n\n"
    
    text += "\n📝 **Чтобы выбрать чат, отправьте его номер** (например: 1, 2, 3)\n"
    text += "Можно выбирать несколько чатов, отправляя номера по одному."
    
    temp_data = db.get_temp_data(user_id)
    temp_data['offset'] = offset
    db.save_temp_data(user_id, temp_data)
    
    has_more = (offset + CHATS_PER_PAGE) < total_chats
    
    await message.reply_text(text, reply_markup=get_chat_selection_keyboard(has_more, MAX_CHATS_PER_REACTION))

async def show_selected_reaction_chats_summary(client, message, user_id, account_id):
    selected = db.get_selected_chats(user_id, account_id)
    
    if not selected:
        await message.reply_text("❌ **Вы не выбрали ни одного чата.**", reply_markup=get_functions_keyboard())
        return
    
    if len(selected) > MAX_CHATS_PER_REACTION:
        await message.reply_text(
            f"❌ **Выбрано слишком много чатов** ({len(selected)}).\nМаксимум: {MAX_CHATS_PER_REACTION}",
            reply_markup=get_functions_keyboard()
        )
        return
    
    temp_data = db.get_temp_data(user_id)
    temp_data['reaction_chats'] = selected
    temp_data['step'] = 'selecting_reaction'
    db.save_temp_data(user_id, temp_data)
    
    chat_list = "\n".join([f"• {chat['chat_title']}" for chat in selected])
    
    await message.reply_text(
        f"✅ **Выбрано чатов:** {len(selected)}\n\n{chat_list}\n\n❤️ **Выберите реакцию:**",
        reply_markup=get_reactions_keyboard()
    )

# Проверка спамблока
@app.on_message(filters.text & filters.regex("^🤖 Проверка спамблока$"))
async def spamblock_check_start(client: Client, message: Message):
    user_id = message.from_user.id
    accounts = db.get_user_accounts(user_id)
    
    if len(accounts) == 0:
        await message.reply_text("❌ **У вас нет добавленных аккаунтов.**", reply_markup=get_functions_keyboard())
        return
    
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

# Рассылка
@app.on_message(filters.text & filters.regex("^📨 Рассылка$"))
async def mailing_start(client: Client, message: Message):
    user_id = message.from_user.id
    active_account = db.get_active_account(user_id)
    
    if not active_account:
        await message.reply_text("❌ **Сначала выберите активный аккаунт!**", reply_markup=get_main_keyboard())
        return
    
    active_mailing = db.get_active_mailing(user_id)
    if active_mailing:
        await message.reply_text(
            "⚠️ **У вас уже есть активная рассылка!**\n\nСначала дождитесь её завершения.",
            reply_markup=get_main_keyboard()
        )
        return
    
    status_msg = await message.reply_text(
        "🔄 **Загружаю список ваших чатов...**\n\nЭто может занять некоторое время.",
        reply_markup=get_back_keyboard()
    )
    
    user_client = await get_user_client(user_id, active_account, db)
    if not user_client:
        await status_msg.edit_text(
            "❌ **Не удалось подключиться к аккаунту.**\n\nПопробуйте добавить его заново.",
            reply_markup=get_functions_keyboard()
        )
        return
    
    try:
        all_chats = []
        async for dialog in user_client.get_dialogs():
            if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                all_chats.append({
                    'id': dialog.chat.id,
                    'title': dialog.chat.title or "Без названия",
                    'type': str(dialog.chat.type).split('.')[-1]
                })
        
        if not all_chats:
            await status_msg.edit_text(
                "❌ **У вас нет групп или каналов для рассылки.**",
                reply_markup=get_functions_keyboard()
            )
            return
        
        db.save_chats(user_id, active_account['id'], all_chats)
        db.clear_selected_chats(user_id, active_account['id'])
        
        await status_msg.delete()
        
        db.save_temp_data(user_id, {
            "step": "selecting_chats",
            "account_id": active_account['id'],
            "offset": 0,
            "selected_chats": []
        })
        
        await show_chats_page(client, message, user_id, active_account['id'], 0)
        
    except Exception as e:
        await status_msg.edit_text(
            f"❌ **Ошибка при загрузке чатов:**\n`{str(e)}`",
            reply_markup=get_functions_keyboard()
        )

async def show_chats_page(client, message, user_id, account_id, offset):
    chats = db.get_chats(user_id, account_id, offset, CHATS_PER_PAGE)
    total_chats = db.get_total_chats_count(user_id, account_id)
    selected = db.get_selected_chats(user_id, account_id)
    
    if not chats:
        if offset == 0:
            await message.reply_text("❌ **Чаты не найдены.**", reply_markup=get_functions_keyboard())
        else:
            await show_selected_chats_summary(client, message, user_id, account_id)
        return
    
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
    
    temp_data = db.get_temp_data(user_id)
    temp_data['offset'] = offset
    db.save_temp_data(user_id, temp_data)
    
    has_more = (offset + CHATS_PER_PAGE) < total_chats
    
    await message.reply_text(text, reply_markup=get_chat_selection_keyboard(has_more))

async def show_selected_chats_summary(client, message, user_id, account_id):
    selected = db.get_selected_chats(user_id, account_id)
    
    if not selected:
        await message.reply_text("❌ **Вы не выбрали ни одного чата.**", reply_markup=get_functions_keyboard())
        return
    
    if len(selected) > MAX_CHATS_PER_MAILING:
        await message.reply_text(
            f"❌ **Выбрано слишком много чатов** ({len(selected)}).\nМаксимум: {MAX_CHATS_PER_MAILING}",
            reply_markup=get_functions_keyboard()
        )
        return
    
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

async def show_mailing_settings(client, message, user_id):
    temp_data = db.get_temp_data(user_id)
    messages = temp_data.get('messages', [])
    send_mode = temp_data.get('send_mode', 'sequential')
    auto_subscribe = temp_data.get('auto_subscribe', False)
    
    mode_display = "📋 По очереди" if send_mode == 'sequential' else "🎲 Рандомно"
    auto_display = "✅ Вкл" if auto_subscribe else "❌ Выкл"
    
    text = f"⚙️ **Настройки рассылки**\n\n📝 **Сообщений:** {len(messages)} шт.\n"
    if messages:
        text += f"   Первое: `{messages[0][:50]}`...\n"
    
    text += f"🔄 **Режим:** {mode_display}\n⚡ **Автоподписка:** {auto_display}\n\nИспользуйте кнопки ниже для настройки: 👇"
    
    await message.reply_text(text, reply_markup=get_mailing_settings_keyboard())

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
        f"📝 **Введите сообщения для рассылки**\n\nОтправляйте по одному сообщению.\nМаксимум: {MAX_CHATS_PER_MAILING} сообщений\n\nКогда закончите, отправьте **/done**",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/done")], [KeyboardButton("❌ Отмена")]], resize_keyboard=True)
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
    
    temp_data['step'] = 'waiting_message_count'
    db.save_temp_data(user_id, temp_data)
    
    await message.reply_text(
        f"✏️ **Сколько сообщений отправить в каждый чат?**\n\n(от 1 до {MAX_CHATS_PER_MAILING})",
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
    
    step = temp_data.get('step')
    
    if step == 'selecting_reaction_chats':
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

# Обработчик текстовых сообщений
@app.on_message(filters.text & ~filters.regex("^(📱 Менеджер аккаунтов|⚙️ Функции|👤 Мой профиль|📢 Наш канал|➕ Добавить аккаунт|📋 Список аккаунтов|🔑 Выбрать активный аккаунт|❌ Удалить аккаунт|🔄 Обновить данные|◀️ Назад в главное меню|◀️ Назад|❌ Отмена|📨 Рассылка|📢 Создание каналов|👥 Создание групп|❤️ Масс-реакции|🤖 Проверка спамблока|📥 Загрузить ещё чаты|✅ Завершить выбор и продолжить|📝 Ввести сообщения|✅ Запустить рассылку|✅ Да|❌ Нет|/done|/stop_reactions)$") & ~filters.regex("^🔄 Режим:.*$") & ~filters.regex("^⚡ Автоподписка:.*$") & ~filters.regex("^[⬜✅] .* - .*$") & ~filters.regex("^✅ Начать проверку$") & ~filters.regex("^👍 Лайк|👎 Дизлайк|❤️ Сердечко|🔥 Огонь|🎉 Праздник$"))
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
        
        try:
            temp_client = Client(
                f"temp_{user_id}",
                api_id=BOT_API_ID,
                api_hash=BOT_API_HASH,
                in_memory=True
            )
            
            await temp_client.connect()
            sent_code = await temp_client.send_code(phone)
            
            temp_data['temp_client'] = True
            temp_data['phone_code_hash'] = sent_code.phone_code_hash
            db.save_temp_data(user_id, temp_data)
            
            user_clients[f"temp_{user_id}"] = temp_client
            
            await message.reply_text(
                "✅ **Код подтверждения отправлен на ваш телефон!**\n\n✏️ **Введите код из SMS:**"
            )
            
        except PhoneNumberInvalid:
            await message.reply_text(
                "❌ **Неверный формат номера телефона.**\n\nПопробуйте снова.",
                reply_markup=get_account_manager_keyboard()
            )
            db.clear_temp_data(user_id)
        except Exception as e:
            await message.reply_text(
                f"❌ **Ошибка:** `{str(e)}`",
                reply_markup=get_account_manager_keyboard()
            )
            db.clear_temp_data(user_id)
    
    elif step == "waiting_code":
        code = text.strip()
        temp_data['code'] = code
        db.save_temp_data(user_id, temp_data)
        
        temp_client = user_clients.get(f"temp_{user_id}")
        if not temp_client:
            await message.reply_text("❌ **Ошибка сессии.**\nНачните заново.", reply_markup=get_account_manager_keyboard())
            db.clear_temp_data(user_id)
            return
        
        try:
            await temp_client.sign_in(
                phone_number=temp_data['phone'],
                phone_code_hash=temp_data['phone_code_hash'],
                phone_code=code
            )
            
            me = await temp_client.get_me()
            session_string = await temp_client.export_session_string()
            
            account_id = db.add_account(
                user_id,
                temp_data['phone'],
                session_string,
                me.username or ""
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
            
            await message.reply_text(f"✅ **Аккаунт успешно добавлен{active_status}!**", reply_markup=get_account_manager_keyboard())
            
        except SessionPasswordNeeded:
            temp_data['step'] = "waiting_2fa"
            db.save_temp_data(user_id, temp_data)
            
            await message.reply_text(
                "🔐 **Требуется двухфакторная аутентификация.**\n\nВведите ваш пароль:"
            )
            
        except PhoneCodeInvalid:
            await message.reply_text("❌ **Неверный код.**\nПопробуйте снова:")
            
        except FloodWait as e:
            await message.reply_text(f"❌ **Слишком много попыток.**\nПодождите {e.value} секунд.")
            
        except Exception as e:
            await message.reply_text(f"❌ **Ошибка:** `{str(e)}`", reply_markup=get_account_manager_keyboard())
            db.clear_temp_data(user_id)
    
    elif step == "waiting_2fa":
        password = text.strip()
        temp_client = user_clients.get(f"temp_{user_id}")
        
        if not temp_client:
            await message.reply_text("❌ **Ошибка сессии.**")
            return
        
        try:
            await temp_client.check_password(password)
            
            me = await temp_client.get_me()
            session_string = await temp_client.export_session_string()
            
            account_id = db.add_account(
                user_id,
                temp_data['phone'],
                session_string,
                me.username or ""
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
            
            await message.reply_text(f"✅ **Аккаунт успешно добавлен{active_status}!**", reply_markup=get_account_manager_keyboard())
            
        except Exception as e:
            await message.reply_text(f"❌ **Ошибка:** `{str(e)}`", reply_markup=get_cancel_keyboard())
    
    elif step == "deleting_account":
        if text.isdigit():
            index = int(text) - 1
            accounts = temp_data.get('accounts', [])
            
            if 0 <= index < len(accounts):
                selected_account = accounts[index]
                db.delete_account(user_id, selected_account['id'])
                await stop_user_client(user_id, selected_account['id'])
                db.clear_temp_data(user_id)
                
                await message.reply_text(f"✅ **Аккаунт {selected_account['account_name']} удален.**", reply_markup=get_account_manager_keyboard())
            else:
                await message.reply_text("❌ **Неверный номер.** Попробуйте снова:")
        else:
            await message.reply_text("❌ **Пожалуйста, отправьте номер аккаунта** (1, 2, 3...):")
    
    elif step == "selecting_account":
        if text.isdigit():
            index = int(text) - 1
            accounts = temp_data.get('accounts', [])
            
            if 0 <= index < len(accounts):
                selected_account = accounts[index]
                db.set_active_account(user_id, selected_account['id'])
                db.clear_temp_data(user_id)
                
                await message.reply_text(f"✅ **Аккаунт {selected_account['account_name']} теперь активен.**", reply_markup=get_account_manager_keyboard())
            else:
                await message.reply_text("❌ **Неверный номер.** Попробуйте снова:")
        else:
            await message.reply_text("❌ **Пожалуйста, отправьте номер аккаунта** (1, 2, 3...):")
    
    elif step in ["selecting_chats", "selecting_reaction_chats"]:
        if text.isdigit():
            chat_number = int(text)
            account_id = temp_data.get('account_id')
            offset = temp_data.get('offset', 0)
            max_chats = temp_data.get('max_chats', MAX_CHATS_PER_MAILING)
            
            if not account_id:
                await message.reply_text("❌ Ошибка. Начните заново.")
                return
            
            chats = db.get_chats(user_id, account_id, 0, 1000)
            if 1 <= chat_number <= len(chats):
                selected_chat = chats[chat_number - 1]
                
                new_status = not selected_chat['selected']
                db.select_chat(user_id, account_id, selected_chat['chat_id'], new_status)
                
                selected = db.get_selected_chats(user_id, account_id)
                if len(selected) > max_chats:
                    db.select_chat(user_id, account_id, selected_chat['chat_id'], False)
                    await message.reply_text(f"❌ **Нельзя выбрать больше {max_chats} чатов!**")
                else:
                    status_text = "добавлен в список" if new_status else "удален из списка"
                    await message.reply_text(
                        f"✅ **Чат '{selected_chat['chat_title']}' {status_text}.**\n"
                        f"📊 **Выбрано:** {len(selected)}/{max_chats}"
                    )
                
                if step == 'selecting_reaction_chats':
                    await show_reaction_chats_page(client, message, user_id, account_id, offset)
                else:
                    await show_chats_page(client, message, user_id, account_id, offset)
            else:
                await message.reply_text(f"❌ **Чат с номером {chat_number} не найден.**")
        else:
            await message.reply_text("❌ **Пожалуйста, отправьте номер чата.**")
    
    elif step == "entering_messages":
        messages = temp_data.get('temp_messages', [])
        if len(messages) < MAX_CHATS_PER_MAILING:
            messages.append(text)
            temp_data['temp_messages'] = messages
            db.save_temp_data(user_id, temp_data)
            await message.reply_text(f"✅ **Сообщение {len(messages)} сохранено.**\nОтправьте следующее или /done")
        else:
            await message.reply_text(f"❌ **Достигнут лимит сообщений** ({MAX_CHATS_PER_MAILING})")
    
    elif step == "waiting_message_count":
        if text.isdigit() and 1 <= int(text) <= MAX_CHATS_PER_MAILING:
            temp_data['message_count'] = int(text)
            temp_data['step'] = 'waiting_delay'
            db.save_temp_data(user_id, temp_data)
            
            await message.reply_text(
                f"✅ **Будет отправлено {text} сообщений в каждый чат.**\n\n"
                f"✏️ **Введите задержку между сообщениями** (в секундах, можно дробное число):"
            )
        else:
            await message.reply_text(f"❌ **Введите число от 1 до {MAX_CHATS_PER_MAILING}:**")
    
    elif step == "waiting_delay":
        try:
            delay = float(text)
            if delay < 0:
                raise ValueError()
            
            temp_data['delay'] = delay
            db.save_temp_data(user_id, temp_data)
            
            await execute_mailing(client, message, user_id, temp_data)
            
        except ValueError:
            await message.reply_text("❌ **Введите корректное число** (например: 5 или 2.5):")
    
    elif step in ["creating_channel", "creating_group"]:
        temp_data['title'] = text
        temp_data['step'] = 'waiting_creation_count'
        db.save_temp_data(user_id, temp_data)
        
        chat_type = "каналов" if step == "creating_channel" else "групп"
        
        await message.reply_text(
            f"✅ **Название сохранено:** `{text}`\n\n"
            f"✏️ **Сколько {chat_type} создать?**\n(от 1 до 50)",
            reply_markup=get_cancel_keyboard()
        )
    
    elif step == "waiting_creation_count":
        if text.isdigit() and 1 <= int(text) <= 50:
            temp_data['count'] = int(text)
            temp_data['step'] = 'waiting_archive'
            db.save_temp_data(user_id, temp_data)
            
            await message.reply_text(
                f"✅ **Будет создано:** {text}\n\n"
                f"📦 **Отправлять в архив после создания?**\n"
                f"(✅ Да / ❌ Нет)",
                reply_markup=get_yes_no_keyboard()
            )
        else:
            await message.reply_text("❌ **Введите число от 1 до 50:**")
    
    elif step == "waiting_archive":
        if text in ["✅ Да", "❌ Нет"]:
            temp_data['archive'] = (text == "✅ Да")
            temp_data['step'] = 'waiting_welcome'
            db.save_temp_data(user_id, temp_data)
            
            await message.reply_text(
                f"✅ **Архивация:** {'✅ Да' if temp_data['archive'] else '❌ Нет'}\n\n"
                f"📝 **Отправлять приветственное сообщение?**\n"
                f"(✅ Да / ❌ Нет)",
                reply_markup=get_yes_no_keyboard()
            )
        else:
            await message.reply_text("❌ Пожалуйста, выберите ✅ Да или ❌ Нет")
    
    elif step == "waiting_welcome":
        if text in ["✅ Да", "❌ Нет"]:
            temp_data['welcome'] = (text == "✅ Да")
            
            if temp_data['welcome']:
                temp_data['step'] = 'waiting_welcome_text'
                db.save_temp_data(user_id, temp_data)
                
                await message.reply_text(
                    "📝 **Введите текст приветственного сообщения:**",
                    reply_markup=get_cancel_keyboard()
                )
            else:
                await execute_creation(client, message, user_id, temp_data, db)
        else:
            await message.reply_text("❌ Пожалуйста, выберите ✅ Да или ❌ Нет")
    
    elif step == "waiting_welcome_text":
        temp_data['welcome_text'] = text
        db.save_temp_data(user_id, temp_data)
        
        await execute_creation(client, message, user_id, temp_data, db)

# Обработчик для выбора реакции
@app.on_message(filters.text & filters.regex("^👍 Лайк|👎 Дизлайк|❤️ Сердечко|🔥 Огонь|🎉 Праздник$"))
async def handle_reaction_selection(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text
    temp_data = db.get_temp_data(user_id)
    
    if temp_data.get('step') != 'selecting_reaction':
        return
    
    selected_reaction = None
    for reaction in AVAILABLE_REACTIONS:
        if reaction['name'] == text:
            selected_reaction = reaction['emoji']
            break
    
    if not selected_reaction:
        return
    
    temp_data['reaction'] = selected_reaction
    db.save_temp_data(user_id, temp_data)
    
    await start_mass_reactions(client, message, user_id, temp_data, db)

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
    
    await check_spamblock(client, message, user_id, selected_accounts, db)
    db.clear_temp_data(user_id)

# Callback обработчики
@app.on_callback_query()
async def handle_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data == "buy_subscription":
        await show_subscription_plans(callback_query)
    
    elif data.startswith("plan_"):
        plan_type = data.replace("plan_", "")
        await show_plan_details(callback_query, plan_type, db)
    
    elif data == "pay_usdt":
        await create_payment_invoice(callback_query, "USDT", db)
    
    elif data == "pay_ton":
        await create_payment_invoice(callback_query, "TON", db)
    
    elif data.startswith("check_invoice_"):
        invoice_id = data.replace("check_invoice_", "")
        await check_invoice(callback_query, invoice_id, db)
    
    elif data == "check_payment":
        await show_payment_history(callback_query, db)
    
    elif data == "back_to_profile":
        await show_profile(client, callback_query, user_id, db)

# Функция рассылки
async def execute_mailing(client, message, user_id, temp_data, db):
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
    
    has_subscription = db.check_subscription(user_id)
    
    if not has_subscription:
        messages = [msg + PROMO_TEXT for msg in messages]
        await client.send_message(
            user_id,
            "⚡ **У вас бесплатная подписка.**\n"
            "К сообщениям добавлена реклама бота.\n"
            "Купите подписку в профиле, чтобы убрать рекламу!"
        )
    
    user_client = await get_user_client(user_id, active_account, db)
    if not user_client:
        await message.reply_text("❌ Не удалось подключиться к аккаунту.")
        return
    
    mailing_id = db.create_active_mailing(
        user_id, account_id, messages, chats, send_mode, 
        message_count, delay, auto_subscribe
    )
    
    mode_display = "📋 По очереди" if send_mode == 'sequential' else "🎲 Рандомно"
    auto_display = "✅ Вкл" if auto_subscribe else "❌ Выкл"
    
    await message.reply_text(
        f"🚀 **Запускаю рассылку...**\n\n"
        f"📊 **Параметры:**\n"
        f"• Чатов: {len(chats)}\n"
        f"• Сообщений в чат: {message_count}\n"
        f"• Режим: {mode_display}\n"
        f"• Задержка: {delay} сек\n"
        f"• Автоподписка: {auto_display}\n\n"
        "Я буду сообщать о прогрессе.",
        reply_markup=get_main_keyboard()
    )
    
    if send_mode == 'sequential':
        await sequential_mailing(client, user_id, user_client, mailing_id, 
                                 messages, chats, message_count, delay, auto_subscribe, db)
    else:
        await random_mailing(client, user_id, user_client, mailing_id,
                             messages, chats, message_count, delay, auto_subscribe, db)

async def sequential_mailing(client, user_id, user_client, mailing_id,
                            messages, chats, message_count, delay, auto_subscribe, db):
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
                message_text = random.choice(messages)
                
                sent = await user_client.send_message(chat_id, message_text)
                sent_messages += 1
                current_message_index = msg_num
                
                db.increment_messages_sent(user_id)
                
                if auto_subscribe and sent.reply_markup:
                    await check_and_process_buttons(
                        client, user_id, user_client, mailing_id,
                        chat_id, sent.id, sent.reply_markup, db
                    )
                
                if sent_messages % 5 == 0 or sent_messages == total_messages:
                    await client.send_message(
                        user_id,
                        f"📊 **Прогресс:** {sent_messages}/{total_messages}\n"
                        f"📍 **Текущий чат:** {chat_title} ({msg_num}/{message_count})"
                    )
                
                db.update_mailing_progress(mailing_id, current_chat_index, current_message_index, sent_messages)
                
                await asyncio.sleep(delay)
                
            except FloodWait as e:
                wait_time = e.value
                await client.send_message(
                    user_id,
                    f"⚠️ **Флуд контроль в чате** {chat_title}.\nОжидание {wait_time} секунд..."
                )
                await asyncio.sleep(wait_time)
                message_text = random.choice(messages)
                sent = await user_client.send_message(chat_id, message_text)
                sent_messages += 1
                db.increment_messages_sent(user_id)
                
                if auto_subscribe and sent.reply_markup:
                    await check_and_process_buttons(
                        client, user_id, user_client, mailing_id,
                        chat_id, sent.id, sent.reply_markup, db
                    )
                
            except PeerIdInvalid:
                await client.send_message(
                    user_id,
                    f"❌ **Недействительный ID чата** {chat_title}. Пропускаю..."
                )
                
            except Exception as e:
                await client.send_message(
                    user_id,
                    f"❌ **Ошибка в чате** {chat_title}: `{str(e)}`"
                )
            
            await asyncio.sleep(1)
        
        await asyncio.sleep(2)
    
    db.complete_mailing(mailing_id)
    
    if auto_subscribe:
        pending_tasks = db.get_pending_auto_subscribe_tasks(mailing_id)
        if pending_tasks:
            await client.send_message(
                user_id,
                f"🔔 **Найдено {len(pending_tasks)} задач на автоподписку.**\nОбрабатываю..."
            )
            
            for task in pending_tasks:
                try:
                    if task['button_data'] and task['button_data'].get('type') == 'callback':
                        await user_client.request_callback_answer(
                            chat_id=int(task['chat_id']),
                            message_id=task['message_id'],
                            callback_data=task['button_data']['data']
                        )
                    elif task['button_data'] and task['button_data'].get('type') == 'url':
                        await client.send_message(
                            user_id,
                            f"🔗 **Найдена ссылка для подписки:**\n{task['button_data']['url']}"
                        )
                    
                    db.complete_auto_subscribe_task(task['id'])
                    
                    await client.send_message(
                        user_id,
                        f"✅ **Выполнена подписка по кнопке** в чате {task['chat_id']}"
                    )
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    await client.send_message(
                        user_id,
                        f"❌ **Ошибка автоподписки:** `{str(e)}`"
                    )
    
    await client.send_message(
        user_id,
        f"✅ **Рассылка завершена!**\n\n"
        f"📊 **Отправлено сообщений:** {sent_messages}/{total_messages}",
        reply_markup=get_main_keyboard()
    )
    
    db.clear_temp_data(user_id)

async def random_mailing(client, user_id, user_client, mailing_id,
                        messages, chats, message_count, delay, auto_subscribe, db):
    total_messages = len(chats) * message_count
    sent_messages = 0
    
    all_messages_to_send = []
    for chat in chats:
        for _ in range(message_count):
            all_messages_to_send.append(chat)
    
    random.shuffle(all_messages_to_send)
    
    current_message_index = 0
    
    for chat in all_messages_to_send:
        try:
            chat_title = chat['chat_title']
            chat_id = int(chat['chat_id'])
            current_message_index += 1
            
            message_text = random.choice(messages)
            
            sent = await user_client.send_message(chat_id, message_text)
            sent_messages += 1
            db.increment_messages_sent(user_id)
            
            if auto_subscribe and sent.reply_markup:
                await check_and_process_buttons(
                    client, user_id, user_client, mailing_id,
                    chat_id, sent.id, sent.reply_markup, db
                )
            
            if sent_messages % 5 == 0 or sent_messages == total_messages:
                await client.send_message(
                    user_id,
                    f"📊 **Прогресс:** {sent_messages}/{total_messages}\n"
                    f"📍 **Текущий чат:** {chat_title}"
                )
            
            db.update_mailing_progress(mailing_id, 0, current_message_index, sent_messages)
            
            await asyncio.sleep(delay)
            
        except FloodWait as e:
            wait_time = e.value
            await client.send_message(
                user_id,
                f"⚠️ **Флуд контроль.** Ожидание {wait_time} секунд..."
            )
            await asyncio.sleep(wait_time)
            message_text = random.choice(messages)
            sent = await user_client.send_message(chat_id, message_text)
            sent_messages += 1
            db.increment_messages_sent(user_id)
            
            if auto_subscribe and sent.reply_markup:
                await check_and_process_buttons(
                    client, user_id, user_client, mailing_id,
                    chat_id, sent.id, sent.reply_markup, db
                )
            
        except PeerIdInvalid:
            await client.send_message(
                user_id,
                f"❌ **Недействительный ID чата** {chat_title}. Пропускаю..."
            )
            
        except Exception as e:
            await client.send_message(
                user_id,
                f"❌ **Ошибка в чате** {chat_title}: `{str(e)}`"
            )
        
        await asyncio.sleep(1)
    
    db.complete_mailing(mailing_id)
    
    if auto_subscribe:
        pending_tasks = db.get_pending_auto_subscribe_tasks(mailing_id)
        if pending_tasks:
            await client.send_message(
                user_id,
                f"🔔 **Найдено {len(pending_tasks)} задач на автоподписку.**\nОбрабатываю..."
            )
            
            for task in pending_tasks:
                try:
                    if task['button_data'] and task['button_data'].get('type') == 'callback':
                        await user_client.request_callback_answer(
                            chat_id=int(task['chat_id']),
                            message_id=task['message_id'],
                            callback_data=task['button_data']['data']
                        )
                    elif task['button_data'] and task['button_data'].get('type') == 'url':
                        await client.send_message(
                            user_id,
                            f"🔗 **Найдена ссылка для подписки:**\n{task['button_data']['url']}"
                        )
                    
                    db.complete_auto_subscribe_task(task['id'])
                    
                    await client.send_message(
                        user_id,
                        f"✅ **Выполнена подписка по кнопке** в чате {task['chat_id']}"
                    )
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    await client.send_message(
                        user_id,
                        f"❌ **Ошибка автоподписки:** `{str(e)}`"
                    )
    
    await client.send_message(
        user_id,
        f"✅ **Рассылка завершена!**\n\n"
        f"📊 **Отправлено сообщений:** {sent_messages}/{total_messages}",
        reply_markup=get_main_keyboard()
    )
    
    db.clear_temp_data(user_id)

async def check_and_process_buttons(client, user_id, user_client, mailing_id,
                                   chat_id, message_id, reply_markup, db):
    try:
        for row in reply_markup.inline_keyboard:
            for button in row:
                button_data = None
                
                if button.url and ("t.me" in button.url or "telegram" in button.url):
                    button_data = {
                        'type': 'url',
                        'url': button.url,
                        'text': button.text
                    }
                elif button.callback_data:
                    button_data = {
                        'type': 'callback',
                        'data': button.callback_data,
                        'text': button.text
                    }
                else:
                    continue
                
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
                    f"🔍 **Найдена кнопка для подписки** в чате {chat_id}: {button.text}\n"
                    f"⏳ Будет обработано после завершения рассылки."
                )
                
    except Exception as e:
        print(f"Ошибка при проверке кнопок: {e}")

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
