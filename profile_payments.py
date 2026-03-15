from datetime import datetime
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import get_payment_methods_keyboard
from config import SUBSCRIPTION_PLANS, EXCHANGE_RATES, MAX_ACCOUNTS_FREE, MAX_ACCOUNTS_PAID
from utils import create_crypto_invoice, check_invoice_status

async def show_profile(client, callback_query, user_id, db):
    """Показать профиль пользователя"""
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
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

async def show_subscription_plans(callback_query):
    """Показать тарифы подписки"""
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

async def show_plan_details(callback_query, plan_type, db):
    """Показать детали тарифа"""
    plan = SUBSCRIPTION_PLANS[plan_type]
    
    db.save_temp_data(callback_query.from_user.id, {"selected_plan": plan_type})
    
    text = (
        f"💎 **Тариф:** {plan['name']}\n"
        f"💰 **Цена:** {plan['price_rub']}₽\n\n"
        f"💱 **Выберите валюту для оплаты:**\n\n"
        f"• USDT: 1 USDT = {EXCHANGE_RATES['USDT']}₽\n"
        f"• TON: 1 TON = {EXCHANGE_RATES['TON']}₽"
    )
    
    await callback_query.message.edit_text(text, reply_markup=get_payment_methods_keyboard())

async def create_payment_invoice(callback_query, currency, db):
    """Создать счет на оплату"""
    user_id = callback_query.from_user.id
    temp_data = db.get_temp_data(user_id)
    plan_type = temp_data.get("selected_plan")
    
    if not plan_type:
        await callback_query.answer("❌ Ошибка выбора тарифа")
        return
    
    plan = SUBSCRIPTION_PLANS[plan_type]
    
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

async def check_invoice(callback_query, invoice_id, db):
    """Проверить статус счета"""
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

async def show_payment_history(callback_query, db):
    """Показать историю платежей"""
    user_id = callback_query.from_user.id
    
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
