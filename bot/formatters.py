from core.config import STATUSES, DEVICE_TYPES, PRIORITIES


def fmt_order_card(order: dict) -> str:
    client = order.get("clients") or {}
    master = order.get("users") or {}
    status = STATUSES.get(order["status"], order["status"])
    device_type = DEVICE_TYPES.get(order["device_type"], order["device_type"])
    priority = "🚨 Срочный" if order.get("priority") == "urgent" else ""

    price = order.get("price", 0)
    prepay = order.get("prepayment", 0)
    parts = order.get("parts_cost", 0)
    balance = price - prepay

    lines = [
        f"📋 *Заказ {order['order_num']}* {priority}",
        f"",
        f"👤 Клиент: {client.get('name', '—')}",
        f"📞 Телефон: {client.get('phone', '—')}",
        f"",
        f"📱 Устройство: {device_type} {order.get('device_brand','')} {order.get('device_model','')}".strip(),
        f"🔧 Неисправность: {order.get('malfunction', '—')}",
        f"",
        f"📊 Статус: {status}",
        f"👨‍🔧 Мастер: {master.get('name', 'Не назначен')}",
    ]

    if order.get("deadline"):
        lines.append(f"⏰ Срок: {order['deadline'][:10]}")

    lines += [
        f"",
        f"💰 Цена ремонта: {price:,} ₽",
        f"💳 Предоплата:   {prepay:,} ₽",
        f"🛒 Запчасти:     {parts:,} ₽",
        f"📌 К доплате:    {balance:,} ₽",
    ]

    # Начисление мастеру
    from db.queries import get_earning_by_order
    earning = get_earning_by_order(order["id"])
    if earning and earning.get("master_amount", 0) > 0:
        lines.append(f"💼 Начислено мастеру: {earning['master_amount']} €")

    if order.get("comment"):
        lines.append(f"\n💬 {order['comment']}")

    return "\n".join(lines)


def fmt_orders_list(orders: list, title: str = "Заказы") -> str:
    if not orders:
        return f"*{title}*\n\nНет активных заказов."

    status_emoji = {
        "new": "🆕", "diagnosis": "🔍", "waiting_parts": "⏳",
        "in_repair": "🔧", "done": "✅", "issued": "📦",
    }
    lines = [f"*{title}* — всего {len(orders)}\n"]
    for o in orders:
        client = o.get("clients") or {}
        e = status_emoji.get(o["status"], "•")
        name = client.get("name", "?")
        model = f"{o.get('device_brand','')} {o.get('device_model','')}".strip() or o["device_type"]
        lines.append(f"{e} `{o['order_num']}` — {name} | {model}")

    lines.append("\n_Используйте /order НОМЕР для деталей_")
    return "\n".join(lines)


def fmt_cash_summary(summary: dict, days: int) -> str:
    income = summary["income"]
    expense = summary["expense"]
    profit = summary["profit"]

    return (
        f"💼 *Касса за {days} дней*\n\n"
        f"📈 Приход:  {income:,} ₽\n"
        f"📉 Расход:  {expense:,} ₽\n"
        f"{'━' * 20}\n"
        f"💰 Прибыль: {profit:,} ₽"
    )


def fmt_master_stats(stats: dict, name: str, days: int) -> str:
    return (
        f"📊 *Статистика — {name}* (за {days} дней)\n\n"
        f"📋 Всего заказов:  {stats['total']}\n"
        f"✅ Выполнено:      {stats['done']}\n"
        f"🔧 В работе:       {stats['in_progress']}\n"
        f"💰 Выручка:        {stats['revenue']:,} ₽"
    )
