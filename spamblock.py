import asyncio
from pyrogram import Client
from pyrogram.errors import UserIsBlocked
from utils import get_user_client

async def check_spamblock(client, message, user_id, selected_accounts, db):
    """Проверка спамблока для выбранных аккаунтов"""
    
    results = []
    
    for acc_data in selected_accounts:
        accounts = db.get_user_accounts(user_id)
        account = next((a for a in accounts if a['id'] == acc_data['id']), None)
        
        if not account:
            results.append(f"❌ {acc_data['name']}: аккаунт не найден")
            continue
        
        user_client = await get_user_client(user_id, account, db)
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
