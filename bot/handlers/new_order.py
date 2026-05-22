from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.queries import find_or_create_client, create_order, get_all_masters, assign_master
from bot.keyboards.kb import device_type_keyboard, priority_keyboard, masters_keyboard, main_menu
from bot.formatters import fmt_order_card
from db.queries import get_order_by_id

router = Router()


class NewOrder(StatesGroup):
    client_name   = State()
    client_phone  = State()
    device_type   = State()
    device_brand  = State()
    device_model  = State()
    malfunction   = State()
    price         = State()
    priority      = State()
    master        = State()
    confirm       = State()


@router.message(F.text == "➕ Новый заказ")
async def start_new_order(msg: Message, state: FSMContext, db_user: dict):
    await state.clear()
    await state.update_data(created_by=db_user["id"])
    await msg.answer("👤 Введите *имя клиента*:", parse_mode="Markdown")
    await state.set_state(NewOrder.client_name)


@router.message(NewOrder.client_name)
async def got_client_name(msg: Message, state: FSMContext):
    await state.update_data(client_name=msg.text.strip())
    await msg.answer("📞 Введите *номер телефона* клиента:", parse_mode="Markdown")
    await state.set_state(NewOrder.client_phone)


@router.message(NewOrder.client_phone)
async def got_client_phone(msg: Message, state: FSMContext):
    phone = msg.text.strip()
    await state.update_data(client_phone=phone)
    await msg.answer("📱 Выберите *тип устройства*:", reply_markup=device_type_keyboard(), parse_mode="Markdown")
    await state.set_state(NewOrder.device_type)


@router.callback_query(NewOrder.device_type, F.data.startswith("dtype:"))
async def got_device_type(cb: CallbackQuery, state: FSMContext):
    dtype = cb.data.split(":")[1]
    await state.update_data(device_type=dtype)
    await cb.message.edit_text("🏷 Введите *бренд* устройства (Apple, Samsung, Lenovo и т.д.):", parse_mode="Markdown")
    await state.set_state(NewOrder.device_brand)


@router.message(NewOrder.device_brand)
async def got_device_brand(msg: Message, state: FSMContext):
    await state.update_data(device_brand=msg.text.strip())
    await msg.answer("📋 Введите *модель* устройства (iPhone 14, Galaxy S23 и т.д.):", parse_mode="Markdown")
    await state.set_state(NewOrder.device_model)


@router.message(NewOrder.device_model)
async def got_device_model(msg: Message, state: FSMContext):
    await state.update_data(device_model=msg.text.strip())
    await msg.answer("🔧 Опишите *неисправность*:", parse_mode="Markdown")
    await state.set_state(NewOrder.malfunction)


@router.message(NewOrder.malfunction)
async def got_malfunction(msg: Message, state: FSMContext):
    await state.update_data(malfunction=msg.text.strip())
    await msg.answer(
        "💰 Введите *предварительную стоимость* ремонта в рублях\n"
        "(или 0, если цена ещё неизвестна):",
        parse_mode="Markdown"
    )
    await state.set_state(NewOrder.price)


@router.message(NewOrder.price)
async def got_price(msg: Message, state: FSMContext):
    try:
        price = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите число, например: 2500")
        return
    await state.update_data(price=price)
    await msg.answer("🚨 Выберите *приоритет*:", reply_markup=priority_keyboard(), parse_mode="Markdown")
    await state.set_state(NewOrder.priority)


@router.callback_query(NewOrder.priority, F.data.startswith("priority:"))
async def got_priority(cb: CallbackQuery, state: FSMContext):
    priority = cb.data.split(":")[1]
    await state.update_data(priority=priority)

    masters = get_all_masters()
    if masters:
        await cb.message.edit_text(
            "👨‍🔧 Выберите *мастера* или пропустите:",
            reply_markup=masters_keyboard(masters, prefix="neworder_master"),
            parse_mode="Markdown"
        )
        await state.set_state(NewOrder.master)
    else:
        await _create_order_final(cb.message, state)


@router.callback_query(NewOrder.master, F.data.startswith("neworder_master:"))
async def got_master(cb: CallbackQuery, state: FSMContext):
    master_id = cb.data.split(":")[1]
    await state.update_data(master_id=master_id)
    await _create_order_final(cb.message, state)


async def _create_order_final(msg, state: FSMContext):
    data = await state.get_data()

    client = find_or_create_client(data["client_name"], data["client_phone"])

    order_data = {
        "client_id":    client["id"],
        "created_by":   data["created_by"],
        "master_id":    data.get("master_id"),
        "device_type":  data["device_type"],
        "device_brand": data["device_brand"],
        "device_model": data["device_model"],
        "malfunction":  data["malfunction"],
        "price":        data["price"],
        "priority":     data["priority"],
        "status":       "new" if not data.get("master_id") else "diagnosis",
    }

    order = create_order(order_data)
    order_full = get_order_by_id(order["id"])

    await state.clear()
    await msg.answer(
        f"✅ *Заказ создан!*\n\n{fmt_order_card(order_full)}",
        parse_mode="Markdown"
    )
