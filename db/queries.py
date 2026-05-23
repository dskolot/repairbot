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
