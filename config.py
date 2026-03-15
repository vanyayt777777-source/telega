import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Конфигурация бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_API_ID = 32480523
BOT_API_HASH = "147839735c9fa4e83451209e9b55cfc5"
CRYPTO_BOT_API_KEY = "550080:AAtZpSCWuiY8cCQiKva4aHTU09b1teG2Rw6"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

MAX_ACCOUNTS_FREE = 3
MAX_ACCOUNTS_PAID = 10
MAX_CHATS_PER_MAILING = 100
MAX_CHATS_PER_REACTION = 3
CHATS_PER_PAGE = 10
DATABASE_PATH = "vest_soft.db"

# Короткое рекламное сообщение
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

# Тарифы подписок
SUBSCRIPTION_PLANS = {
    "1day": {"name": "1 день", "price_rub": 3, "duration_days": 1},
    "7days": {"name": "7 дней", "price_rub": 10, "duration_days": 7},
    "forever": {"name": "Навсегда", "price_rub": 40, "duration_days": 99999}
}

# Курсы валют
EXCHANGE_RATES = {
    "USDT": 90,
    "TON": 120
}
