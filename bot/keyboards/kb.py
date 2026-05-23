from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from core.config import STATUSES, DEVICE_TYPES, PRIORITIES, CASH_TYPES


def main_menu(role: str) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="🔍 Найти заказ")]]

    if role in ("admin", "owner"):
        buttons.append([KeyboardButton(text="➕ Новый заказ"), KeyboardButton(text="📊 Все заказы")])
        buttons.append([KeyboardButton(text="💰 Касса"), KeyboardButton(text="📈 Статистика")])

    if role == "master":
        buttons.append([KeyboardButton(text="➕ Новый заказ")])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def status_keyboard(order_id: str, current_status: str) -> InlineKeyboardMarkup:
    from core.config import STATUS_ORDER
    buttons = []
    for s, label in STATUSES.items():
        if s == current_status:
            continue
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"set_status:{order_id}:{s}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def order_actions(order_id: str, role: str) -> InlineKeyboardMarkup:
    btns = [
        [InlineKeyboardButton(text="🔄 Изменить статус", callback_data=f"change_status:{order_id}")],
        [InlineKeyboardButton(text="🔧 Запчасти", callback_data=f"parts:{order_id}")],
        [InlineKeyboardButton(text="💰 Добавить оплату", callback_data=f"pay:{order_id}")],
    ]
    if role in ("admin", "owner"):
        btns.append([InlineKeyboardButton(text="👤 Назначить мастера", callback_data=f"assign:{order_id}")])
        btns.append([InlineKeyboardButton(text="✏️ Изменить цену", callback_data=f"edit_price:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def device_type_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=label, callback_data=f"dtype:{key}")]
               for key, label in DEVICE_TYPES.items()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def priority_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=label, callback_data=f"priority:{key}")]
               for key, label in PRIORITIES.items()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def masters_keyboard(masters: list, prefix: str = "master") -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=m["name"], callback_data=f"{prefix}:{m['id']}")]
               for m in masters]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cash_type_keyboard(order_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="💰 Полная оплата",  callback_data=f"cash:payment_in:{order_id}")],
        [InlineKeyboardButton(text="💳 Предоплата",     callback_data=f"cash:prepayment_in:{order_id}")],
        [InlineKeyboardButton(text="🛒 Расход/запчасть",callback_data=f"cash:expense:{order_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def parts_keyboard(parts: list, order_id: str) -> InlineKeyboardMarkup:
    btns = []
    for p in parts:
        status_emoji = {"needed": "🔴", "ordered": "🟡", "arrived": "🟢", "installed": "✅"}.get(p["status"], "")
        short_part_id = p['id'][:8]
        short_order_id = order_id[:8]
        btns.append([InlineKeyboardButton(
            text=f"{status_emoji} {p['name']} — {p['cost']} €",
            callback_data=f"ps:{short_part_id}:{short_order_id}"
        )])
    btns.append([InlineKeyboardButton(text="➕ Добавить запчасть", callback_data=f"add_part:{order_id[:8]}")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def part_status_keyboard(part_id: str, order_id: str) -> InlineKeyboardMarkup:
    statuses = [
        ("ordered",   "🟡 Заказана"),
        ("arrived",   "🟢 Пришла"),
        ("installed", "✅ Установлена"),
    ]
    btns = [[InlineKeyboardButton(text=label, callback_data=f"set_part:{part_id}:{s}:{order_id}")]
            for s, label in statuses]
    btns.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"parts:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def confirm_keyboard(yes_data: str, no_data: str = "cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data=yes_data),
        InlineKeyboardButton(text="❌ Отмена", callback_data=no_data),
    ]])
