import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

STATUSES = {
    "new":            "🆕 Новый",
    "diagnosis":      "🔍 Диагностика",
    "waiting_parts":  "⏳ Ждём запчасть",
    "in_repair":      "🔧 В ремонте",
    "done":           "✅ Готово",
    "issued":         "📦 Выдано",
    "cancelled":      "❌ Отменено",
}

STATUS_ORDER = ["new", "diagnosis", "waiting_parts", "in_repair", "done", "issued"]

DEVICE_TYPES = {
    "phone":   "📱 Телефон",
    "laptop":  "💻 Ноутбук",
    "tablet":  "📲 Планшет",
    "pc":      "🖥 Компьютер",
}

PRIORITIES = {
    "normal": "Обычный",
    "urgent": "🚨 Срочный",
}

CASH_TYPES = {
    "payment_in":    "💰 Оплата",
    "prepayment_in": "💳 Предоплата",
    "expense":       "🛒 Расход",
    "salary":        "👤 Зарплата",
    "other_in":      "➕ Прочий приход",
    "other_out":     "➖ Прочий расход",
}

# Типы прихода (увеличивают баланс)
INCOME_TYPES = {"payment_in", "prepayment_in", "other_in"}
