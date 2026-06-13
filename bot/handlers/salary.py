from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.queries import (
    get_master_salary_summary, update_earning_loss,
    get_all_masters, add_cash_entry, get_order_by_num,
    create_manual_earning
)

router = Router()


# ── МОЙ ЗАРАБОТОК ───────────────────────────────────────────

@router.message(F.text == "💵 Мой заработок")
async def my_earnings(msg: Message, db_user: dict):
    summary = get_master_salary_summary(db_user["id"], days=90)
    earnings = summary["earnings"]
    lines = ["💵 Мой заработок за 90 дней\n"]
    if not earnings:
        lines.append("Начислений пока нет.")
    else:
        for e in earnings:
            loss = e["master_loss_amount"]
            loss_str = f" (вычет: -{loss} €)" if loss > 0 else ""
            note = e.get("note") or ""
            note_str = f" | {note}" if note else ""
            lines.append(f"• {e['order_num']} — начислено {e['master_amount']} €{loss_str}{note_str}")
    lines += [
        f"\nНачислено итого: {summary['net_earned']} €",
        f"Выплачено:       {summary['total_paid']} €",
    ]
    balance = summary["balance"]
    if balance > 0:
        lines.append(f"К выплате:       {balance} €")
    elif balance < 0:
        lines.append(f"Долг кассе:      {abs(balance)} €")
    else:
        lines.append("Расчёт закрыт ✅")
    await msg.answer("\n".join(lines))


# ── ЗАРПЛАТА МАСТЕРОВ (администратор) ───────────────────────

@router.message(F.text == "👨‍🔧 Зарплата мастеров")
async def masters_salary(msg: Message, user_role: str):
    if user_role not in ("admin", "owner"):
        await msg.answer("❌ Недостаточно прав.")
        return
    masters = get_all_masters()
    if not masters:
        await msg.answer("Мастеров не найдено.")
        return
    lines = ["👨‍🔧 Сводка по мастерам за 90 дней\n"]
    for m in masters:
        s = get_master_salary_summary(m["id"], days=90)
        balance = s["balance"]
        if balance > 0:
            bal_str = f"к выплате: {balance} €"
        elif balance < 0:
            bal_str = f"должен кассе: {abs(balance)} €"
        else:
            bal_str = "расчёт закрыт"
        lines.append(f"👤 {m['name']}\n   Начислено: {s['net_earned']} € | Выплачено: {s['total_paid']} € | {bal_str}\n")
    from bot.keyboards.kb import masters_salary_keyboard
    await msg.answer("\n".join(lines), reply_markup=masters_salary_keyboard(masters))


# ── ДЕТАЛИЗАЦИЯ ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("salary_detail:"))
async def salary_detail(cb: CallbackQuery):
    master_id = cb.data.split(":")[1]
    summary = get_master_salary_summary(master_id, days=90)
    earnings = summary["earnings"]
    if not earnings:
        await cb.message.answer("Начислений нет.")
        await cb.answer()
        return
    lines = ["📋 Детализация начислений:\n"]
    for e in earnings:
        loss = e["master_loss_amount"]
        loss_str = f" | вычет: {loss} €" if loss > 0 else ""
        note = e.get("note") or ""
        note_str = f" | {note}" if note else ""
        lines.append(f"• {e['order_num']} — {e['master_amount']} €{loss_str}{note_str}")
    await cb.message.answer("\n".join(lines))
    await cb.answer()


# ── НАЧИСЛИТЬ ВРУЧНУЮ ────────────────────────────────────────

class ManualEarning(StatesGroup):
    order_num = State()
    amount    = State()
    note      = State()


@router.callback_query(F.data.startswith("earn_manual:"))
async def earn_manual_start(cb: CallbackQuery, state: FSMContext, user_role: str):
    if user_role not in ("admin", "owner"):
        await cb.answer("❌ Недостаточно прав", show_alert=True)
        return
    master_id = cb.data.split(":")[1]
    await state.update_data(master_id=master_id)
    await cb.message.answer("📋 Введите номер заказа (например SC-0003):")
    await state.set_state(ManualEarning.order_num)
    await cb.answer()


@router.message(ManualEarning.order_num)
async def earn_manual_order(msg: Message, state: FSMContext):
    order = get_order_by_num(msg.text.strip().upper())
    if not order:
        await msg.answer("❌ Заказ не найден. Проверьте номер.")
        return
    price = order.get("price", 0) or 0
    parts = order.get("parts_cost", 0) or 0
    profit = price - parts
    await state.update_data(
        order_id=order["id"],
        order_num=order["order_num"],
        repair_price=price,
        parts_cost=parts,
    )
    await msg.answer(
        f"Заказ {order['order_num']}\n"
        f"Цена ремонта: {price} €\n"
        f"Запчасти: {parts} €\n"
        f"Прибыль: {profit} €\n\n"
        f"💰 Введите сумму начисления мастеру в евро:"
    )
    await state.set_state(ManualEarning.amount)


@router.message(ManualEarning.amount)
async def earn_manual_amount(msg: Message, state: FSMContext):
    try:
        amount = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите число, например: 25")
        return
    await state.update_data(amount=amount)
    await msg.answer("📝 Добавьте комментарий (или - чтобы пропустить):")
    await state.set_state(ManualEarning.note)


@router.message(ManualEarning.note)
async def earn_manual_confirm(msg: Message, state: FSMContext):
    note = msg.text.strip() if msg.text.strip() != "-" else ""
    data = await state.get_data()
    await state.clear()
    create_manual_earning(
        order_id=data["order_id"],
        master_id=data["master_id"],
        order_num=data["order_num"],
        repair_price=data["repair_price"],
        parts_cost=data["parts_cost"],
        master_amount=data["amount"],
        note=note,
    )
    masters = get_all_masters()
    master = next((m for m in masters if m["id"] == data["master_id"]), None)
    name = master["name"] if master else "Мастер"
    await msg.answer(
        f"✅ Начислено {data['amount']} € мастеру {name}\n"
        f"Заказ: {data['order_num']}"
        + (f"\nКомментарий: {note}" if note else "")
    )


# ── РАЗДЕЛИТЬ УБЫТОК ─────────────────────────────────────────

class SplitLoss(StatesGroup):
    select_order  = State()
    enter_percent = State()


@router.callback_query(F.data.startswith("split_loss:"))
async def split_loss_start(cb: CallbackQuery, state: FSMContext, user_role: str):
    if user_role not in ("admin", "owner"):
        await cb.answer("❌ Недостаточно прав", show_alert=True)
        return
    master_id = cb.data.split(":")[1]
    summary = get_master_salary_summary(master_id, days=90)
    loss_orders = [e for e in summary["earnings"] if e["profit"] < 0]
    if not loss_orders:
        await cb.message.answer("У этого мастера нет убыточных заказов.")
        await cb.answer()
        return
    from bot.keyboards.kb import loss_orders_keyboard
    await cb.message.answer("Выберите убыточный заказ:", reply_markup=loss_orders_keyboard(loss_orders))
    await state.update_data(earnings=loss_orders)
    await state.set_state(SplitLoss.select_order)
    await cb.answer()


@router.callback_query(SplitLoss.select_order, F.data.startswith("loss_order:"))
async def split_loss_order(cb: CallbackQuery, state: FSMContext):
    earning_id = cb.data.split(":")[1]
    await state.update_data(earning_id=earning_id)
    await cb.message.answer(
        "Какой % убытка списать на мастера?\n"
        "(0 = весь берёт компания, 100 = весь на мастере)\n"
        "Введите число от 0 до 100:"
    )
    await state.set_state(SplitLoss.enter_percent)
    await cb.answer()


@router.message(SplitLoss.enter_percent)
async def split_loss_apply(msg: Message, state: FSMContext):
    try:
        percent = int(msg.text.strip())
        if not 0 <= percent <= 100:
            raise ValueError
    except ValueError:
        await msg.answer("❌ Введите число от 0 до 100")
        return
    data = await state.get_data()
    update_earning_loss(data["earning_id"], percent)
    await state.clear()
    await msg.answer(f"✅ На мастера: {percent}% | На компанию: {100 - percent}%")


# ── ВЫПЛАТИТЬ ЗАРПЛАТУ ───────────────────────────────────────

class PaySalary(StatesGroup):
    master_id = State()
    amount    = State()


@router.callback_query(F.data.startswith("pay_salary:"))
async def pay_salary_start(cb: CallbackQuery, state: FSMContext, user_role: str):
    if user_role not in ("admin", "owner"):
        await cb.answer("❌ Недостаточно прав", show_alert=True)
        return
    master_id = cb.data.split(":")[1]
    summary = get_master_salary_summary(master_id, days=90)
    await state.update_data(master_id=master_id)
    await cb.message.answer(
        f"К выплате мастеру: {summary['balance']} €\n"
        f"Введите сумму выплаты в евро:"
    )
    await state.set_state(PaySalary.amount)
    await cb.answer()


@router.message(PaySalary.amount)
async def pay_salary_confirm(msg: Message, state: FSMContext):
    try:
        amount = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите число, например: 150")
        return
    data = await state.get_data()
    add_cash_entry(
        user_id=data["master_id"],
        type_="salary",
        amount=amount,
        description="Выплата зарплаты"
    )
    await state.clear()
    await msg.answer(f"✅ Зарплата {amount} € выплачена и списана с кассы.")


# ── НАЧИСЛИТЬ ПРЯМО ИЗ КАРТОЧКИ ЗАКАЗА ──────────────────────

class EarnFromOrder(StatesGroup):
    amount   = State()
    note     = State()


@router.callback_query(F.data.startswith("earn_order:"))
async def earn_from_order_start(cb: CallbackQuery, state: FSMContext, user_role: str):
    if user_role not in ("admin", "owner"):
        await cb.answer("❌ Недостаточно прав", show_alert=True)
        return
    _, short_order_id, short_master_id = cb.data.split(":")
    from db.queries import get_order_by_short_id, get_all_masters
    order = get_order_by_short_id(short_order_id)
    if not order:
        await cb.answer("Заказ не найден", show_alert=True)
        return
    # Получаем полный master_id из заказа
    master_id = order.get("master_id") or short_master_id
    price = order.get("price", 0) or 0
    parts = order.get("parts_cost", 0) or 0
    profit = price - parts
    # Проверяем есть ли уже начисление
    from db.queries import get_earning_by_order
    existing = get_earning_by_order(order_id)
    existing_str = f"\n(уже начислено: {existing['master_amount']} €)" if existing else ""
    await state.update_data(
        order_id=order_id,
        master_id=master_id,
        order_num=order["order_num"],
        repair_price=price,
        parts_cost=parts,
    )
    await cb.message.answer(
        f"Заказ {order['order_num']}{existing_str}\n"
        f"Цена ремонта: {price} €\n"
        f"Запчасти: {parts} €\n"
        f"Прибыль: {profit} €\n\n"
        f"💰 Введите сумму начисления мастеру в евро:"
    )
    await state.set_state(EarnFromOrder.amount)
    await cb.answer()


@router.message(EarnFromOrder.amount)
async def earn_from_order_amount(msg: Message, state: FSMContext):
    try:
        amount = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите число, например: 25")
        return
    await state.update_data(amount=amount)
    await msg.answer("📝 Комментарий (или - чтобы пропустить):")
    await state.set_state(EarnFromOrder.note)


@router.message(EarnFromOrder.note)
async def earn_from_order_confirm(msg: Message, state: FSMContext):
    note = msg.text.strip() if msg.text.strip() != "-" else ""
    data = await state.get_data()
    await state.clear()
    create_manual_earning(
        order_id=data["order_id"],
        master_id=data["master_id"],
        order_num=data["order_num"],
        repair_price=data["repair_price"],
        parts_cost=data["parts_cost"],
        master_amount=data["amount"],
        note=note,
    )
    await msg.answer(
        f"✅ Начислено {data['amount']} € мастеру\n"
        f"Заказ: {data['order_num']}"
        + (f"\nКомментарий: {note}" if note else "")
    )
