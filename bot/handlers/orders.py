from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.queries import (
    get_active_orders, get_order_by_num, get_order_by_id,
    update_order_status, update_order_field, assign_master, get_all_masters
)
from bot.keyboards.kb import order_actions, status_keyboard, masters_keyboard
from bot.formatters import fmt_orders_list, fmt_order_card

router = Router()


# ── СПИСОК ЗАКАЗОВ ──────────────────────────────────────────

@router.message(F.text == "📋 Мои заказы")
async def my_orders(msg: Message, db_user: dict, user_role: str):
    if user_role == "master":
        orders = get_active_orders(master_id=db_user["id"])
        title = "Мои активные заказы"
    else:
        orders = get_active_orders()
        title = "Все активные заказы"
    await msg.answer(fmt_orders_list(orders, title), parse_mode="Markdown")


@router.message(F.text == "📊 Все заказы")
async def all_orders(msg: Message, user_role: str):
    if user_role not in ("admin", "owner"):
        await msg.answer("❌ Недостаточно прав.")
        return
    orders = get_active_orders()
    await msg.answer(fmt_orders_list(orders, "Все активные заказы"), parse_mode="Markdown")


# ── ПОИСК ЗАКАЗА ────────────────────────────────────────────

class SearchOrder(StatesGroup):
    waiting_num = State()


@router.message(F.text == "🔍 Найти заказ")
async def search_order_prompt(msg: Message, state: FSMContext):
    await msg.answer("🔍 Введите номер заказа (например: *SC-0042*):", parse_mode="Markdown")
    await state.set_state(SearchOrder.waiting_num)


@router.message(SearchOrder.waiting_num)
async def search_order_result(msg: Message, state: FSMContext, db_user: dict, user_role: str):
    await state.clear()
    num = msg.text.strip().upper().replace(" ", "")
    order = get_order_by_num(num)
    if not order:
        await msg.answer("❌ Заказ не найден. Проверьте номер.")
        return
    await _show_order(msg, order, db_user, user_role)


@router.message(Command("order"))
async def order_by_command(msg: Message, db_user: dict, user_role: str):
    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer("Используйте: /order SC-0042")
        return
    order = get_order_by_num(parts[1])
    if not order:
        await msg.answer("❌ Заказ не найден.")
        return
    await _show_order(msg, order, db_user, user_role)


async def _show_order(msg: Message, order: dict, db_user: dict, user_role: str):
    text = fmt_order_card(order)
    kb = order_actions(order["id"], user_role)
    await msg.answer(text, reply_markup=kb, parse_mode="Markdown")


# ── СМЕНА СТАТУСА ───────────────────────────────────────────

@router.callback_query(F.data.startswith("change_status:"))
async def change_status_menu(cb: CallbackQuery):
    order_id = cb.data.split(":")[1]
    order = get_order_by_id(order_id)
    if not order:
        await cb.answer("Заказ не найден", show_alert=True)
        return
    await cb.message.edit_text(
        f"🔄 Выберите новый статус для *{order['order_num']}*:",
        reply_markup=status_keyboard(order_id, order["status"]),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("set_status:"))
async def set_status(cb: CallbackQuery, db_user: dict, user_role: str):
    _, order_id, new_status = cb.data.split(":")
    order = update_order_status(order_id, new_status, db_user["id"])
    await cb.message.edit_text(
        fmt_order_card(order),
        reply_markup=order_actions(order_id, user_role),
        parse_mode="Markdown"
    )
    await cb.answer("✅ Статус обновлён")


# ── НАЗНАЧИТЬ МАСТЕРА ───────────────────────────────────────

@router.callback_query(F.data.startswith("assign:"))
async def assign_master_menu(cb: CallbackQuery, user_role: str):
    if user_role not in ("admin", "owner"):
        await cb.answer("❌ Недостаточно прав", show_alert=True)
        return
    order_id = cb.data.split(":")[1]
    masters = get_all_masters()
    await cb.message.edit_text(
        "👨‍🔧 Выберите мастера:",
        reply_markup=masters_keyboard(masters, prefix=f"do_assign:{order_id}")
    )


@router.callback_query(F.data.startswith("do_assign:"))
async def do_assign_master(cb: CallbackQuery, user_role: str):
    parts = cb.data.split(":")
    order_id = parts[1]
    master_id = parts[2]
    order = assign_master(order_id, master_id)
    await cb.message.edit_text(
        fmt_order_card(order),
        reply_markup=order_actions(order_id, user_role),
        parse_mode="Markdown"
    )
    await cb.answer("✅ Мастер назначен")


# ── ИЗМЕНИТЬ ЦЕНУ ───────────────────────────────────────────

class EditPrice(StatesGroup):
    waiting_price = State()
    order_id = State()


@router.callback_query(F.data.startswith("edit_price:"))
async def edit_price_prompt(cb: CallbackQuery, state: FSMContext, user_role: str):
    if user_role not in ("admin", "owner"):
        await cb.answer("❌ Недостаточно прав", show_alert=True)
        return
    order_id = cb.data.split(":")[1]
    await state.update_data(order_id=order_id, user_role=user_role)
    await cb.message.answer("✏️ Введите новую стоимость ремонта (в рублях):")
    await state.set_state(EditPrice.waiting_price)


@router.message(EditPrice.waiting_price)
async def set_price(msg: Message, state: FSMContext, db_user: dict):
    try:
        price = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите число, например: 3500")
        return
    data = await state.get_data()
    order_id = data["order_id"]
    user_role = data.get("user_role", "master")
    order = update_order_field(order_id, "price", price)
    await state.clear()
    await msg.answer(
        fmt_order_card(order),
        reply_markup=order_actions(order_id, user_role),
        parse_mode="Markdown"
    )
