from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Awaitable, Any
from db.queries import get_user_by_telegram


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        tg_id = str(event.from_user.id)
        user = get_user_by_telegram(tg_id)
        if not user:
            if isinstance(event, Message):
                await event.answer(
                    "❌ У вас нет доступа к этой системе.\n"
                    "Обратитесь к администратору для добавления."
                )
            return
        data["db_user"] = user
        data["user_role"] = user["role"]
        return await handler(event, data)
