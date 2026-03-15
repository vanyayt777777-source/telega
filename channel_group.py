import asyncio
from pyrogram import Client
from pyrogram.errors import FloodWait
from utils import get_user_client

async def execute_creation(client, message, user_id, temp_data, db):
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
    
    user_client = await get_user_client(user_id, active_account, db)
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
                chat = await user_client.create_channel(
                    title=current_title,
                    description=f"Создано через @VestSoftBot"
                )
                chat_type = 'channel'
                db.increment_channels_created(user_id)
            else:
                chat = await user_client.create_group(
                    title=current_title
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
    
    from keyboards import get_main_keyboard
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
