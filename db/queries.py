from supabase import create_client
from core.config import SUPABASE_URL, SUPABASE_KEY, INCOME_TYPES


def get_sb():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def get_user_by_telegram(telegram_id: str):
    try:
        sb = get_sb()
        res = sb.table("users").select("*").eq("telegram_id", str(telegram_id)).execute()
        print(f"[AUTH] tg_id={telegram_id}, found={len(res.data)}")
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[AUTH ERROR] {e}")
        return None


def get_all_masters():
    sb = get_sb()
    res = sb.table("users").select("*").eq("role", "master").execute()
    return res.data


def find_or_create_client(name: str, phone: str):
    sb = get_sb()
    res = sb.table("clients").select("*").eq("phone", phone).execute()
    if res.data:
        return res.data[0]
    new = sb.table("clients").insert({"name": name, "phone": phone}).execute()
    return new.data[0]


def get_client_by_id(client_id: str):
    sb = get_sb()
    res = sb.table("clients").select("*").eq("id", client_id).execute()
    return res.data[0] if res.data else None


def create_order(data: dict):
    sb = get_sb()
    res = sb.table("orders").insert(data).execute()
    return res.data[0]


def get_order_by_id(order_id: str):
    sb = get_sb()
    res = sb.table("orders").select("*, clients(*), users!orders_master_id_fkey(*)").eq("id", order_id).execute()
    return res.data[0] if res.data else None


def get_order_by_num(order_num: str):
    try:
        sb = get_sb()
        num = order_num.strip().upper()
        print(f"[SEARCH] order_num='{num}'")
        res = sb.table("orders").select("*, clients(*), users!orders_master_id_fkey(*)").eq("order_num", num).execute()
        print(f"[SEARCH] found={len(res.data)}")
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"[SEARCH ERROR] {e}")
        return None


def get_active_orders(master_id: str = None):
    sb = get_sb()
    q = sb.table("orders").select("*, clients(name, phone), users!orders_master_id_fkey(name)").not_.in_("status", ["issued", "cancelled"])
    if master_id:
        q = q.eq("master_id", master_id)
    res = q.order("created_at", desc=True).execute()
    return res.data


def update_order_status(order_id: str, new_status: str, changed_by: str, comment: str = ""):
    sb = get_sb()
    order = get_order_by_id(order_id)
    old_status = order["status"] if order else ""
    sb.table("orders").update({"status": new_status}).eq("id", order_id).execute()
    sb.table("order_status_log").insert({
        "order_id": order_id,
        "changed_by": changed_by,
        "old_status": old_status,
        "new_status": new_status,
        "comment": comment,
    }).execute()
    return get_order_by_id(order_id)


def update_order_field(order_id: str, field: str, value):
    sb = get_sb()
    sb.table("orders").update({field: value}).eq("id", order_id).execute()
    return get_order_by_id(order_id)


def assign_master(order_id: str, master_id: str):
    sb = get_sb()
    sb.table("orders").update({"master_id": master_id, "status": "diagnosis"}).eq("id", order_id).execute()
    return get_order_by_id(order_id)


def add_part(order_id: str, name: str, cost: int):
    sb = get_sb()
    res = sb.table("parts").insert({"order_id": order_id, "name": name, "cost": cost}).execute()
    total_parts = sum(p["cost"] for p in get_parts_for_order(order_id))
    sb.table("orders").update({"parts_cost": total_parts}).eq("id", order_id).execute()
    return res.data[0]


def get_parts_for_order(order_id: str):
    sb = get_sb()
    res = sb.table("parts").select("*").eq("order_id", order_id).execute()
    return res.data


def update_part_status(part_id: str, new_status: str):
    sb = get_sb()
    res = sb.table("parts").update({"status": new_status}).eq("id", part_id).execute()
    return res.data[0]


def add_cash_entry(user_id: str, type_: str, amount: int, description: str = "", order_id: str = None):
    sb = get_sb()
    data = {"user_id": user_id, "type": type_, "amount": amount, "description": description}
    if order_id:
        data["order_id"] = order_id
    res = sb.table("cash_log").insert(data).execute()
    return res.data[0]


def get_cash_summary(days: int = 30):
    sb = get_sb()
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    res = sb.table("cash_log").select("*").gte("created_at", since).execute()
    income = sum(e["amount"] for e in res.data if e["type"] in INCOME_TYPES)
    expense = sum(e["amount"] for e in res.data if e["type"] not in INCOME_TYPES)
    return {"income": income, "expense": expense, "profit": income - expense, "entries": res.data}


def get_master_stats(master_id: str, days: int = 30):
    sb = get_sb()
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    res = sb.table("orders").select("*").eq("master_id", master_id).gte("created_at", since).execute()
    orders = res.data
    done = [o for o in orders if o["status"] in ("done", "issued")]
    return {
        "total": len(orders),
        "done": len(done),
        "in_progress": len([o for o in orders if o["status"] not in ("done", "issued", "cancelled")]),
        "revenue": sum(o["price"] for o in done),
    }


def get_orders_stats(days: int = 30):
    sb = get_sb()
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    res = sb.table("orders").select("status, price").gte("created_at", since).execute()
    orders = res.data
    return {
        "total": len(orders),
        "done": len([o for o in orders if o["status"] in ("done", "issued")]),
        "cancelled": len([o for o in orders if o["status"] == "cancelled"]),
        "revenue": sum(o["price"] for o in orders if o["status"] in ("done", "issued")),
    }


def get_order_by_short_id(short_id: str):
    sb = get_sb()
    res = sb.table("orders").select("*").execute()
    for row in res.data:
        if row["id"].startswith(short_id):
            return row
    return None


def get_part_by_short_id(short_id: str):
    sb = get_sb()
    res = sb.table("parts").select("*").execute()
    for row in res.data:
        if row["id"].startswith(short_id):
            return row
    return None


def get_cash_summary_with_orders(days: int = 30):
    sb = get_sb()
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    res = sb.table("cash_log").select("*, orders(order_num)").gte("created_at", since).execute()
    entries = res.data
    from core.config import INCOME_TYPES
    income = sum(e["amount"] for e in entries if e["type"] in INCOME_TYPES)
    expense = sum(e["amount"] for e in entries if e["type"] not in INCOME_TYPES)
    return {"income": income, "expense": expense, "profit": income - expense, "entries": entries}


def get_cash_log_with_orders(days: int = 30):
    sb = get_sb()
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    # Получаем все записи кассы
    res = sb.table("cash_log").select("*").gte("created_at", since).execute()
    entries = res.data

    # Собираем уникальные order_id
    order_ids = list(set(e["order_id"] for e in entries if e.get("order_id")))

    # Получаем номера заказов одним запросом
    order_map = {}
    if order_ids:
        orders_res = sb.table("orders").select("id, order_num").in_("id", order_ids).execute()
        order_map = {o["id"]: o["order_num"] for o in orders_res.data}

    # Добавляем order_num к каждой записи
    for e in entries:
        e["order_num"] = order_map.get(e.get("order_id"), "")

    from core.config import INCOME_TYPES
    income = sum(e["amount"] for e in entries if e["type"] in INCOME_TYPES)
    expense = sum(e["amount"] for e in entries if e["type"] not in INCOME_TYPES)
    return {"income": income, "expense": expense, "profit": income - expense, "entries": entries}


def search_orders(query: str) -> list:
    """Поиск заказов по имени клиента, телефону, модели устройства или запчасти"""
    sb = get_sb()
    q = query.strip().lower()
    results = []
    seen_ids = set()

    # По модели устройства
    r1 = sb.table("orders").select("*, clients(name, phone), users!orders_master_id_fkey(name)").ilike("device_model", f"%{q}%").execute()
    for o in r1.data:
        if o["id"] not in seen_ids:
            results.append(o)
            seen_ids.add(o["id"])

    # По неисправности
    r2 = sb.table("orders").select("*, clients(name, phone), users!orders_master_id_fkey(name)").ilike("malfunction", f"%{q}%").execute()
    for o in r2.data:
        if o["id"] not in seen_ids:
            results.append(o)
            seen_ids.add(o["id"])

    # По имени клиента
    clients = sb.table("clients").select("id, name, phone").ilike("name", f"%{q}%").execute()
    client_ids = [c["id"] for c in clients.data]
    if not client_ids:
        # По телефону
        clients2 = sb.table("clients").select("id").ilike("phone", f"%{q}%").execute()
        client_ids = [c["id"] for c in clients2.data]
    if client_ids:
        r3 = sb.table("orders").select("*, clients(name, phone), users!orders_master_id_fkey(name)").in_("client_id", client_ids).execute()
        for o in r3.data:
            if o["id"] not in seen_ids:
                results.append(o)
                seen_ids.add(o["id"])

    # По названию запчасти
    parts = sb.table("parts").select("order_id").ilike("name", f"%{q}%").execute()
    part_order_ids = list(set(p["order_id"] for p in parts.data))
    if part_order_ids:
        r4 = sb.table("orders").select("*, clients(name, phone), users!orders_master_id_fkey(name)").in_("id", part_order_ids).execute()
        for o in r4.data:
            if o["id"] not in seen_ids:
                results.append(o)
                seen_ids.add(o["id"])

    return results


# ── НАЧИСЛЕНИЯ МАСТЕРАМ ─────────────────────────────────────

def create_earning(order_id: str, master_id: str, order_num: str,
                   repair_price: int, parts_cost: int, master_percent: int = 40):
    sb = get_sb()
    profit = repair_price - parts_cost
    master_amount = max(0, int(profit * master_percent / 100))
    master_loss_amount = abs(min(0, profit))
    data = {
        "order_id":          order_id,
        "master_id":         master_id,
        "order_num":         order_num,
        "repair_price":      repair_price,
        "parts_cost":        parts_cost,
        "profit":            profit,
        "master_percent":    master_percent,
        "master_amount":     master_amount,
        "master_loss_percent": 0,
        "master_loss_amount":  0,
    }
    res = sb.table("master_earnings").insert(data).execute()
    return res.data[0]


def get_earnings_by_master(master_id: str, days: int = 30):
    sb = get_sb()
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    res = sb.table("master_earnings").select("*").eq("master_id", master_id).gte("created_at", since).execute()
    return res.data


def get_all_earnings(days: int = 30):
    sb = get_sb()
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    res = sb.table("master_earnings").select("*, users(name)").gte("created_at", since).execute()
    return res.data


def get_earning_by_order(order_id: str):
    sb = get_sb()
    res = sb.table("master_earnings").select("*").eq("order_id", order_id).execute()
    return res.data[0] if res.data else None


def update_earning_loss(earning_id: str, master_loss_percent: int):
    sb = get_sb()
    earning = sb.table("master_earnings").select("*").eq("id", earning_id).execute().data[0]
    loss = earning.get("master_loss_amount", 0) or abs(min(0, earning["profit"]))
    master_loss_amount = int(loss * master_loss_percent / 100)
    sb.table("master_earnings").update({
        "master_loss_percent": master_loss_percent,
        "master_loss_amount":  master_loss_amount,
    }).eq("id", earning_id).execute()


def get_master_salary_summary(master_id: str, days: int = 30):
    """Сколько заработал, сколько выплачено, сколько должны"""
    sb = get_sb()
    from datetime import datetime, timedelta
    from core.config import INCOME_TYPES
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    earnings = sb.table("master_earnings").select("*").eq("master_id", master_id).gte("created_at", since).execute().data
    total_earned = sum(e["master_amount"] for e in earnings)
    total_loss   = sum(e["master_loss_amount"] for e in earnings)
    net_earned   = total_earned - total_loss

    # Выплаченные зарплаты из кассы
    paid = sb.table("cash_log").select("amount").eq("user_id", master_id).eq("type", "salary").gte("created_at", since).execute().data
    total_paid = sum(p["amount"] for p in paid)

    balance = net_earned - total_paid
    return {
        "total_earned": total_earned,
        "total_loss":   total_loss,
        "net_earned":   net_earned,
        "total_paid":   total_paid,
        "balance":      balance,
        "earnings":     earnings,
    }
