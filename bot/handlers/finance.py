from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.queries import (
    add_cash_entry, get_cash_summary, get_cash_log_with_orders,
    add_part, get_parts_for_order, update_part_status,
    get_order_by_id, get_master_stats, get_orders_stats
)
from bot.keyboards.kb import cash_type_keyboard, parts_keyboard, part_status_keyboard
from bot.formatters import fmt_cash_summary, fmt_master_stats, fmt_order_card

router = Router()


# ══════════════════════════════════════════
# КАССА — главное меню
# ══════════════════════════════════════════

@router.message(F.text == "💰 Касса")
async def cash_menu(msg: Message, user_role: str):
    if user_role not in ("admin", "owner"):
        await msg.answer("❌ Недостаточно прав.")
        return
    from bot.keyboards.kb import cash_detail_keyboard
    await msg.answer("💼 Касса — выберите раздел:", reply_markup=cash_detail_keyboard())


@router.callback_query(F.data == "cash_summary")
async def show_cash_summary(cb: CallbackQuery):
    summary = get_cash_summary(days=30)
    await cb.message.answer(fmt_cash_summary(summary, days=30))
    await cb.answer()


@router.callback_query(F.data == "cash_income")
async def show_cash_income(cb: CallbackQuery):
    from core.config import INCOME_TYPES
    summary = get_cash_log_with_orders(days=30)
    entries = [e for e in summary["entries"] if e["type"] in INCOME_TYPES]
    if not entries:
        await cb.message.answer("За 30 дней приходов не было.")
        await cb.answer()
        return
    lines = ["📈 Приходы за 30 дней:\n"]
    for e in entries[-20:]:
        date = e["created_at"][:10]
        order_num = e.get("order_num", "")
        order_str = f" ({order_num})" if order_num else ""
        desc = e["description"] or e["type"]
        lines.append(f"{date} | +{e['amount']} € | {desc}{order_str}")
    lines.append(f"\nИтого: {sum(e['amount'] for e in entries)} €")
    await cb.message.answer("\n".join(lines))
    await cb.answer()


@router.callback_query(F.data == "cash_expense")
async def show_cash_expense(cb: CallbackQuery):
    from core.config import INCOME_TYPES
    summary = get_cash_log_with_orders(days=30)
    entries = [e for e in summary["entries"] if e["type"] not in INCOME_TYPES]
    if not entries:
        await cb.message.answer("За 30 дней расходов не было.")
        await cb.answer()
        return
    lines = ["📉 Расходы за 30 дней:\n"]
    for e in entries[-20:]:
        date = e["created_at"][:10]
        order_num = e.get("order_num", "")
        order_str = f" ({order_num})" if order_num else ""
        desc = e["description"] or e["type"]
        lines.append(f"{date} | -{e['amount']} € | {desc}{order_str}")
    lines.append(f"\nИтого: {sum(e['amount'] for e in entries)} €")
    await cb.message.answer("\n".join(lines))
    await cb.answer()


# ══════════════════════════════════════════
# ОПЛАТА ПО ЗАКАЗУ
# ══════════════════════════════════════════

@router.callback_query(F.data.startswith("pay:"))
async def pay_menu(cb: CallbackQuery, user_role: str):
    order_id = cb.data.split(":")[1]
    await cb.message.answer(
        "💰 Выберите тип платежа:",
        reply_markup=cash_type_keyboard(order_id)
    )


class AddPayment(StatesGroup):
    waiting_amount = State()
    cash_type = State()
    order_id = State()


@router.callback_query(F.data.startswith("cash:"))
async def cash_type_selected(cb: CallbackQuery, state: FSMContext):
    _, cash_type, order_id = cb.data.split(":")
    await state.update_data(cash_type=cash_type, order_id=order_id)
    await cb.message.answer("💵 Введите сумму в евро:")
    await state.set_state(AddPayment.waiting_amount)


@router.message(AddPayment.waiting_amount)
async def cash_amount_entered(msg: Message, state: FSMContext, db_user: dict, user_role: str):
    try:
        amount = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите число, например: 50")
        return

    data = await state.get_data()
    cash_type = data["cash_type"]
    order_id = data["order_id"]

    add_cash_entry(
        user_id=db_user["id"],
        type_=cash_type,
        amount=amount,
        order_id=order_id,
        description="Платёж по заказу"
    )

    if cash_type in ("payment_in", "prepayment_in"):
        from db.queries import update_order_field
        order = get_order_by_id(order_id)
        current = order.get("prepayment", 0) or 0
        update_order_field(order_id, "prepayment", current + amount)

    await state.clear()
    order = get_order_by_id(order_id)
    from bot.keyboards.kb import order_actions
    await msg.answer(
        f"✅ Платёж {amount} € зафиксирован.\n\n{fmt_order_card(order)}",
        reply_markup=order_actions(order_id, user_role),
    )


# ══════════════════════════════════════════
# ЗАПЧАСТИ
# ══════════════════════════════════════════

@router.callback_query(F.data.startswith("parts:"))
async def show_parts(cb: CallbackQuery):
    order_id = cb.data.split(":")[1]
    parts = get_parts_for_order(order_id)
    kb = parts_keyboard(parts, order_id)
    if parts:
        lines = ["🔧 Запчасти к заказу:\n"]
        for p in parts:
            status_emoji = {"needed": "🔴", "ordered": "🟡", "arrived": "🟢", "installed": "✅"}.get(p["status"], "")
            lines.append(f"{status_emoji} {p['name']} — {p['cost']} €")
        text = "\n".join(lines)
    else:
        text = "🔧 Запчасти ещё не добавлены."
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


class AddPart(StatesGroup):
    waiting_name = State()
    waiting_cost = State()
    order_id = State()


@router.callback_query(F.data.startswith("add_part:"))
async def add_part_prompt(cb: CallbackQuery, state: FSMContext):
    short_id = cb.data.split(":")[1]
    from db.queries import get_order_by_short_id
    order = get_order_by_short_id(short_id)
    order_id = order["id"] if order else short_id
    await state.update_data(order_id=order_id)
    await cb.message.answer("📦 Введите название запчасти:")
    await state.set_state(AddPart.waiting_name)


@router.message(AddPart.waiting_name)
async def part_name_entered(msg: Message, state: FSMContext):
    await state.update_data(part_name=msg.text.strip())
    await msg.answer("💰 Введите стоимость запчасти в евро:")
    await state.set_state(AddPart.waiting_cost)


@router.message(AddPart.waiting_cost)
async def part_cost_entered(msg: Message, state: FSMContext, db_user: dict):
    try:
        cost = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите число, например: 25")
        return

    data = await state.get_data()
    order_id = data["order_id"]
    part = add_part(order_id, data["part_name"], cost)

    if cost > 0:
        add_cash_entry(
            user_id=db_user["id"],
            type_="expense",
            amount=cost,
            description=f"Запчасть: {data['part_name']}",
            order_id=order_id
        )

    await state.clear()
    parts = get_parts_for_order(order_id)
    await msg.answer(
        f"✅ Запчасть добавлена: {part['name']} — {cost} €\n"
        f"💸 Расход {cost} € записан в кассу.",
        reply_markup=parts_keyboard(parts, order_id),
    )


@router.callback_query(F.data.startswith("ps:"))
async def part_status_menu(cb: CallbackQuery):
    _, short_part_id, short_order_id = cb.data.split(":")
    from db.queries import get_part_by_short_id, get_order_by_short_id
    part = get_part_by_short_id(short_part_id)
    order = get_order_by_short_id(short_order_id)
    if not part or not order:
        await cb.answer("Не найдено", show_alert=True)
        return
    await cb.message.answer(
        f"📦 Запчасть: {part['name']}\nОбновите статус:",
        reply_markup=part_status_keyboard(part["id"], order["id"])
    )
    await cb.answer()


@router.callback_query(F.data.startswith("sp:"))
async def set_part_status(cb: CallbackQuery):
    _, short_part_id, new_status, short_order_id = cb.data.split(":")
    from db.queries import get_part_by_short_id, get_order_by_short_id
    part = get_part_by_short_id(short_part_id)
    order = get_order_by_short_id(short_order_id)
    if not part or not order:
        await cb.answer("Не найдено", show_alert=True)
        return
    update_part_status(part["id"], new_status)
    parts = get_parts_for_order(order["id"])
    await cb.message.answer("✅ Статус обновлён", reply_markup=parts_keyboard(parts, order["id"]))
    await cb.answer()


# ══════════════════════════════════════════
# СТАТИСТИКА
# ══════════════════════════════════════════

@router.message(F.text == "📈 Статистика")
async def stats_menu(msg: Message, db_user: dict, user_role: str):
    if user_role == "master":
        stats = get_master_stats(db_user["id"], days=30)
        text = fmt_master_stats(stats, db_user["name"], days=30)
    else:
        stats = get_orders_stats(days=30)
        cash = get_cash_summary(days=30)
        text = (
            f"Статистика сервиса за 30 дней\n\n"
            f"📋 Всего заказов:  {stats['total']}\n"
            f"✅ Выполнено:      {stats['done']}\n"
            f"❌ Отменено:       {stats['cancelled']}\n"
            f"💰 Выручка:        {stats['revenue']:,} €\n\n"
            f"📈 Приход (касса): {cash['income']:,} €\n"
            f"📉 Расход (касса): {cash['expense']:,} €\n"
            f"💵 Прибыль:        {cash['profit']:,} €"
        )
    await msg.answer(text)


# ══════════════════════════════════════════
# РАСХОДЫ (зарплаты, долги, прочее)
# ══════════════════════════════════════════

class AddExpense(StatesGroup):
    exp_type    = State()
    master_id   = State()
    amount      = State()
    description = State()


EXP_LABELS = {
    "salary":       "Зарплата мастеру",
    "admin_salary": "Зарплата администратору",
    "debt":         "Долг / аванс мастеру",
    "transport":    "Бензин / транспорт",
    "equipment":    "Оборудование",
    "other":        "Прочий расход",
}

NEEDS_MASTER = {"salary", "debt"}


@router.message(F.text == "📤 Расходы")
async def expenses_menu(msg: Message, state: FSMContext, user_role: str):
    if user_role not in ("admin", "owner"):
        await msg.answer("❌ Недостаточно прав.")
        return
    from bot.keyboards.kb import expense_type_keyboard
    await msg.answer("📤 Выберите тип расхода:", reply_markup=expense_type_keyboard())
    await state.set_state(AddExpense.exp_type)


@router.callback_query(AddExpense.exp_type, F.data.startswith("exp:"))
async def exp_type_selected(cb: CallbackQuery, state: FSMContext):
    exp_type = cb.data.split(":")[1]
    await state.update_data(exp_type=exp_type)

    if exp_type in NEEDS_MASTER:
        from db.queries import get_all_masters
        from bot.keyboards.kb import expense_masters_keyboard
        masters = get_all_masters()
        await cb.message.answer("👨‍🔧 Выберите мастера:", reply_markup=expense_masters_keyboard(masters))
        await state.set_state(AddExpense.master_id)
    else:
        await cb.message.answer("💵 Введите сумму в евро:")
        await state.set_state(AddExpense.amount)
    await cb.answer()


@router.callback_query(AddExpense.master_id, F.data.startswith("exp_master:"))
async def exp_master_selected(cb: CallbackQuery, state: FSMContext):
    master_id = cb.data.split(":")[1]
    await state.update_data(master_id=master_id)
    await cb.message.answer("💵 Введите сумму в евро:")
    await state.set_state(AddExpense.amount)
    await cb.answer()


@router.message(AddExpense.amount)
async def exp_amount_entered(msg: Message, state: FSMContext):
    try:
        amount = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите число, например: 50")
        return
    await state.update_data(amount=amount)
    await msg.answer("📝 Добавьте комментарий (или напишите - чтобы пропустить):")
    await state.set_state(AddExpense.description)


@router.message(AddExpense.description)
async def exp_description_entered(msg: Message, state: FSMContext, db_user: dict):
    data = await state.get_data()
    exp_type = data["exp_type"]
    amount   = data["amount"]
    comment  = msg.text.strip() if msg.text.strip() != "-" else ""
    label    = EXP_LABELS.get(exp_type, "Расход")

    description = label
    if comment:
        description += f": {comment}"

    add_cash_entry(
        user_id=db_user["id"],
        type_="salary" if exp_type in ("salary", "admin_salary", "debt") else "other_out",
        amount=amount,
        description=description,
    )

    await state.clear()
    await msg.answer(
        f"✅ Расход зафиксирован\n\n"
        f"📝 {description}\n"
        f"💸 Сумма: {amount} €"
    )
