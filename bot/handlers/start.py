from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards.kb import main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(msg: Message, db_user: dict, user_role: str):
    name = db_user["name"]
    role_label = {"master": "Мастер", "admin": "Администратор", "owner": "Владелец"}.get(user_role, user_role)
    await msg.answer(
        f"👋 Привет, *{name}*!\n"
        f"Роль: {role_label}\n\n"
        f"Выберите действие в меню ниже:",
        reply_markup=main_menu(user_role),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "cancel")
async def cancel_action(cb, state):
    await state.clear()
    await cb.answer("Отменено")
    await cb.message.delete()
