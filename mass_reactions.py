import asyncio
from pyrogram import Client
from utils import get_user_client, active_reaction_tasks

async def start_mass_reactions(client, message, user_id, temp_data, db):
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
    
    user_client = await get_user_client(user_id, active_account, db)
    if not user_client:
        await message.reply_text("❌ Не удалось подключиться к аккаунту.")
        return
    
    reaction_id = db.create_active_reactions(user_id, account_id, chats, reaction)
    
    chat_list = "\n".join([f"• {chat['chat_title']}" for chat in chats])
    
    from keyboards import get_main_keyboard
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
                int(chat['chat_id']), chat['chat_title'], reaction, db
            )
        )
    
    db.clear_temp_data(user_id)

async def monitor_chat_for_reactions(client, user_id, user_client, reaction_id, 
                                     chat_id, chat_title, reaction, db):
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
