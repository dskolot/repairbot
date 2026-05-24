from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.queries import (
    get_earnings_by_master, get_all_earnings, get_earning_by_order,
    get_master_salary_summary, update_earning_loss, get_all_masters,
    add_cash_entry, get_order_by_id, create_earning
)

router = Router()

MASTER_PERCENT = 40  # процент мастера от цены ремонта по умолчанию


# ── НАЧИСЛИТЬ ЗАРАБОТОК ПРИ ВЫДАЧЕ ЗАКАЗА ──────────────────

async def maybe_create_earning(order_id: str, new_status: str):
    """Вызывается при смене статуса — начисляет заработок при статусе 'issued'"""
    if new_status != "issued":
        return
    order = get_order_by_id(order_id)
    if not order or not order.get("master_id"):
        return
    existing = get_earning_by_order(order_id)
    if existing:
        return  # уже начислено
    create_earning(
        order_id=order_id,
        master_id=order["master_id"],
        order_num=order["order_num"],
        repair_price=order.get("price", 0) or 0,
        parts_cost=order.get("parts_cost", 0) or 0,
        master_percent=MASTER_PERCENT,
    )


# ── МОЙ ЗАРАБОТОК (для мастера) ─────────────────────────────

@router.message(F.text == "💵 Мой заработок")
async def my_earnings(msg: Message, db_user: dict):
    summary = get_master_salary_summary(db_user["id"], days=30)
    earnings = summary["earnings"]

    lines = [f"💵 Мой заработок за 30 дней\n"]

    if not earnings:
        lines.append("Завершённых ремонтов пока нет.")
    else:
        for e in earnings:
            profit = e["profit"]
            loss_str = ""
            if profit < 0 and e["master_loss_amount"] > 0:
                loss_str = f" (вычет: -{e['master_loss_amount']} €)"
            lines.append(
                f"• {e['order_num']} | цена {e['repair_price']} € | "
                f"запчасти {e['parts_cost']} € | "
                f"начислено {e['master_amount']} €{loss_str}"
            )

    lines += [
        f"\nИтого начислено:  {summary['net_earned']} €",
        f"Выплачено:        {summary['total_paid']} €",
    ]
    balance = summary["balance"]
    if balance > 0:
        lines.append(f"К выплате:        {balance} €")
    elif balance < 0:
        lines.append(f"Долг кассе:       {abs(balance)} €")
    else:
        lines.append(f"Расчёт закрыт ✅")

    await msg.answer("\n".join(lines))


# ── ЗАРПЛАТА МАСТЕРОВ (для администратора) ──────────────────

@router.message(F.text == "👨‍🔧 Зарплата мастеров")
async def masters_salary(msg: Message, user_role: str):
    if user_role not in ("admin", "owner"):
        await msg.answer("❌ Недостаточно прав.")
        return

    masters = get_all_masters()
    if not masters:
        await msg.answer("Мастеров не найдено.")
        return

    lines = ["👨‍🔧 Сводка по мастерам за 30 дней\n"]
    for m in masters:
        s = get_master_salary_summary(m["id"], days=30)
        balance = s["balance"]
        if balance > 0:
            bal_str = f"к выплате: {balance} €"
        elif balance < 0:
            bal_str = f"должен кассе: {abs(balance)} €"
        else:
            bal_str = "расчёт закрыт"
        lines.append(
            f"👤 {m['name']}\n"
            f"   Начислено: {s['net_earned']} € | "
            f"Выплачено: {s['total_paid']} € | {bal_str}\n"
        )

    from bot.keyboards.kb import masters_salary_keyboard
    await msg.answer("\n".join(lines), reply_markup=masters_salary_keyboard(masters))


# ── ДЕТАЛИЗАЦИЯ ПО МАСТЕРУ ──────────────────────────────────

@router.callback_query(F.data.startswith("salary_detail:"))
async def salary_detail(cb: CallbackQuery, user_role: str):
    master_id = cb.data.split(":")[1]
    summary = get_master_salary_summary(master_id, days=30)
    earnings = summary["earnings"]

    lines = ["📋 Детализация начислений\n"]
    for e in earnings:
        profit = e["profit"]
        status = "убыток" if profit < 0 else "ок"
        loss_str = f" | вычет мастера: {e['master_loss_amount']} €" if e["master_loss_amount"] > 0 else ""
        lines.append(
            f"• {e['order_num']} | {e['repair_price']} € - {e['parts_cost']} € запч = "
            f"прибыль {profit} € ({status}) | начислено {e['master_amount']} €{loss_str}"
        )

    await cb.message.answer("\n".join(lines) if len(lines) > 1 else "Завершённых заказов нет.")
    await cb.answer()


# ── РАЗДЕЛИТЬ УБЫТОК ────────────────────────────────────────

class SplitLoss(StatesGroup):
    select_order = State()
    enter_percent = State()
    earning_id = State()


@router.callback_query(F.data.startswith("split_loss:"))
async def split_loss_start(cb: CallbackQuery, state: FSMContext, user_role: str):
    if user_role not in ("admin", "owner"):
        await cb.answer("❌ Недостаточно прав", show_alert=True)
        return
    master_id = cb.data.split(":")[1]
    summary = get_master_salary_summary(master_id, days=30)
    loss_orders = [e for e in summary["earnings"] if e["profit"] < 0]

    if not loss_orders:
        await cb.message.answer("У этого мастера нет убыточных заказов за 30 дней.")
        await cb.answer()
        return

    from bot.keyboards.kb import loss_orders_keyboard
    await cb.message.answer(
        "Выберите убыточный заказ для распределения:",
        reply_markup=loss_orders_keyboard(loss_orders)
    )
    await state.set_state(SplitLoss.select_order)
    await cb.answer()


@router.callback_query(SplitLoss.select_order, F.data.startswith("loss_order:"))
async def split_loss_order(cb: CallbackQuery, state: FSMContext):
    earning_id = cb.data.split(":")[1]
    await state.update_data(earning_id=earning_id)
    await cb.message.answer(
        "Какой % убытка списать на мастера?\n"
        "(0 = весь убыток берёт компания, 100 = весь на мастере)\n"
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
    earning_id = data["earning_id"]
    update_earning_loss(earning_id, percent)
    await state.clear()

    company_percent = 100 - percent
    await msg.answer(
        f"✅ Убыток распределён:\n"
        f"На мастера: {percent}%\n"
        f"На компанию: {company_percent}%"
    )


# ── ВЫПЛАТИТЬ ЗАРПЛАТУ ──────────────────────────────────────

class PaySalary(StatesGroup):
    master_id = State()
    amount = State()


@router.callback_query(F.data.startswith("pay_salary:"))
async def pay_salary_start(cb: CallbackQuery, state: FSMContext, user_role: str):
    if user_role not in ("admin", "owner"):
        await cb.answer("❌ Недостаточно прав", show_alert=True)
        return
    master_id = cb.data.split(":")[1]
    summary = get_master_salary_summary(master_id, days=30)
    balance = summary["balance"]

    await state.update_data(master_id=master_id)
    await cb.message.answer(
        f"К выплате мастеру: {balance} €\n"
        f"Введите сумму выплаты в евро:"
    )
    await state.set_state(PaySalary.amount)
    await cb.answer()


@router.message(PaySalary.amount)
async def pay_salary_confirm(msg: Message, state: FSMContext, db_user: dict):
    try:
        amount = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите число, например: 150")
        return

    data = await state.get_data()
    master_id = data["master_id"]

    add_cash_entry(
        user_id=master_id,
        type_="salary",
        amount=amount,
        description="Выплата зарплаты"
    )
    await state.clear()
    await msg.answer(f"✅ Зарплата {amount} € выплачена и списана с кассы.")
