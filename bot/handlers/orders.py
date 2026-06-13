from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.queries import (
    get_active_orders, get_order_by_num, get_order_by_id,
    update_order_status, update_order_field, assign_master,
    get_all_masters, search_orders
)
from bot.keyboards.kb import order_actions, status_keyboard, masters_keyboard, orders_list_keyboard
from bot.formatters import fmt_order_card

router = Router()


def show_kb(order: dict, user_role: str):
    """Собирает клавиатуру для карточки заказа с правильными параметрами"""
    return order_actions(
        order["id"],
        user_role,
        status=order.get("status", ""),
        master_id=order.get("master_id") or ""
    )


# ── СПИСОК ЗАКАЗОВ ──────────────────────────────────────────

@router.message(F.text == "📋 Мои заказы")
async def my_orders(msg: Message, db_user: dict, user_role: str):
    if user_role == "master":
        orders = get_active_orders(master_id=db_user["id"])
        title = "Мои активные заказы"
    else:
        orders = get_active_orders()
        title = "Все активные заказы"
    if not orders:
        await msg.answer(f"{title}\n\nНет активных заказов.")
        return
    text = f"{title} — {len(orders)}\n\n"
    for o in orders:
        client = o.get("clients") or {}
        text += f"• {o['order_num']} — {client.get('name','?')} | {o.get('device_model','')}\n"
    await msg.answer(text, reply_markup=orders_list_keyboard(orders))


@router.message(F.text == "📊 Все заказы")
async def all_orders(msg: Message, user_role: str):
    orders = get_active_orders()
    if not orders:
        await msg.answer("Нет активных заказов.")
        return
    text = f"Все активные заказы — {len(orders)}\n\n"
    for o in orders:
        client = o.get("clients") or {}
        text += f"• {o['order_num']} — {client.get('name','?')} | {o.get('device_model','')}\n"
    await msg.answer(text, reply_markup=orders_list_keyboard(orders))


# ── КЛИК ПО ЗАКАЗУ В СПИСКЕ ─────────────────────────────────

@router.callback_query(F.data.startswith("open_order:"))
async def open_order_from_list(cb: CallbackQuery, db_user: dict, user_role: str):
    order_id = cb.data.split(":")[1]
    order = get_order_by_id(order_id)
    if not order:
        await cb.answer("Заказ не найден", show_alert=True)
        return
    await cb.message.answer(fmt_order_card(order), reply_markup=show_kb(order, user_role))
    await cb.answer()


# ── ПОИСК ЗАКАЗА ────────────────────────────────────────────

class SearchOrder(StatesGroup):
    waiting_query = State()


@router.message(F.text == "🔍 Найти заказ")
async def search_order_prompt(msg: Message, state: FSMContext):
    await msg.answer(
        "🔍 Введите для поиска:\n"
        "• Номер заказа (SC-0001)\n"
        "• Имя клиента\n"
        "• Телефон\n"
        "• Модель устройства (iPhone 15)\n"
        "• Название запчасти"
    )
    await state.set_state(SearchOrder.waiting_query)


@router.message(SearchOrder.waiting_query)
async def search_order_result(msg: Message, state: FSMContext, db_user: dict, user_role: str):
    await state.clear()
    query = msg.text.strip()

    # Поиск по номеру заказа
    if query.upper().startswith("SC-"):
        order = get_order_by_num(query)
        if order:
            await msg.answer(fmt_order_card(order), reply_markup=show_kb(order, user_role))
        else:
            await msg.answer("❌ Заказ не найден. Проверьте номер.")
        return

    # Полнотекстовый поиск
    orders = search_orders(query)
    if not orders:
        await msg.answer("❌ Ничего не найдено. Попробуйте другой запрос.")
        return
    if len(orders) == 1:
        order = get_order_by_id(orders[0]["id"])
        await msg.answer(fmt_order_card(order), reply_markup=show_kb(order, user_role))
        return
    text = f"Найдено {len(orders)} заказов:\n\n"
    for o in orders:
        client = o.get("clients") or {}
        text += f"• {o['order_num']} — {client.get('name','?')} | {o.get('device_model','')}\n"
    await msg.answer(text, reply_markup=orders_list_keyboard(orders))


@router.message(Command("order"))
async def order_by_command(msg: Message, db_user: dict, user_role: str):
    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer("Используйте: /order SC-0001")
        return
    order = get_order_by_num(parts[1].upper().strip())
    if not order:
        await msg.answer("❌ Заказ не найден.")
        return
    await msg.answer(fmt_order_card(order), reply_markup=show_kb(order, user_role))


# ── СМЕНА СТАТУСА ───────────────────────────────────────────

@router.callback_query(F.data.startswith("change_status:"))
async def change_status_menu(cb: CallbackQuery):
    order_id = cb.data.split(":")[1]
    order = get_order_by_id(order_id)
    if not order:
        await cb.answer("Заказ не найден", show_alert=True)
        return
    await cb.message.answer(
        f"🔄 Выберите новый статус для {order['order_num']}:",
        reply_markup=status_keyboard(order_id, order["status"])
    )
    await cb.answer()


@router.callback_query(F.data.startswith("set_status:"))
async def set_status(cb: CallbackQuery, db_user: dict, user_role: str):
    _, order_id, new_status = cb.data.split(":")
    order = update_order_status(order_id, new_status, db_user["id"])
    from bot.handlers.salary import maybe_create_earning
    await maybe_create_earning(order_id, new_status)
    await cb.message.answer(fmt_order_card(order), reply_markup=show_kb(order, user_role))
    await cb.answer("✅ Статус обновлён")


# ── НАЗНАЧИТЬ МАСТЕРА ───────────────────────────────────────

@router.callback_query(F.data.startswith("assign:"))
async def assign_master_menu(cb: CallbackQuery, user_role: str):
    order_id = cb.data.split(":")[1]
    masters = get_all_masters()
    await cb.message.answer(
        "👨‍🔧 Выберите мастера:",
        reply_markup=masters_keyboard(masters, prefix=f"do_assign:{order_id}")
    )
    await cb.answer()


@router.callback_query(F.data.startswith("do_assign:"))
async def do_assign_master(cb: CallbackQuery, user_role: str):
    parts = cb.data.split(":")
    order_id  = parts[1]
    master_id = parts[2]
    order = assign_master(order_id, master_id)
    await cb.message.answer(fmt_order_card(order), reply_markup=show_kb(order, user_role))
    await cb.answer("✅ Мастер назначен")


# ── ИЗМЕНИТЬ ЦЕНУ ───────────────────────────────────────────

class EditPrice(StatesGroup):
    waiting_price = State()


@router.callback_query(F.data.startswith("edit_price:"))
async def edit_price_prompt(cb: CallbackQuery, state: FSMContext, user_role: str):
    order_id = cb.data.split(":")[1]
    await state.update_data(order_id=order_id, user_role=user_role)
    await cb.message.answer("✏️ Введите новую стоимость ремонта в евро:")
    await state.set_state(EditPrice.waiting_price)
    await cb.answer()


@router.message(EditPrice.waiting_price)
async def set_price(msg: Message, state: FSMContext):
    try:
        price = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите число, например: 95")
        return
    data = await state.get_data()
    order = update_order_field(data["order_id"], "price", price)
    await state.clear()
    await msg.answer(fmt_order_card(order), reply_markup=show_kb(order, data.get("user_role", "master")))
