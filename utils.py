import asyncio
import aiohttp
import json
from pyrogram import Client
from pyrogram.errors import FloodWait, SessionPasswordNeeded, PhoneCodeInvalid, PhoneNumberInvalid
from config import BOT_API_ID, BOT_API_HASH, CRYPTO_BOT_API_KEY, EXCHANGE_RATES, SUBSCRIPTION_PLANS

# Словарь для хранения клиентов пользователей
user_clients = {}
active_reaction_tasks = {}

async def get_user_client(user_id: int, account: dict, db) -> Optional[Client]:
    """Получить или создать клиент для аккаунта пользователя"""
    client_key = f"{user_id}_{account['id']}"
    
    if client_key in user_clients:
        try:
            await user_clients[client_key].get_me()
            return user_clients[client_key]
        except:
            try:
                await user_clients[client_key].stop()
            except:
                pass
            del user_clients[client_key]
    
    client = Client(
        f"user_{user_id}_{account['id']}",
        api_id=BOT_API_ID,
        api_hash=BOT_API_HASH,
        session_string=account['session_string'],
        in_memory=True
    )
    
    try:
        await client.start()
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
    
    if currency == "USDT":
        crypto_amount = round(amount / EXCHANGE_RATES["USDT"], 2)
        asset = "USDT"
    else:
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
