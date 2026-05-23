from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Awaitable, Any
import asyncio
from db.queries import get_user_by_telegram


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        tg_id = str(event.from_user.id)
        try:
            user = await asyncio.get_event_loop().run_in_executor(
                None, get_user_by_telegram, tg_id
            )
        except Exception as e:
            print(f"Auth error for {tg_id}: {e}")
            user = None

        if not user:
            print(f"User not found: {tg_id}")
            if isinstance(event, Message):
                await event.answer(
                    "❌ У вас нет доступа к этой системе.\n"
                    "Обратитесь к администратору для добавления."
                )
            return
        data["db_user"] = user
        data["user_role"] = user["role"]
        return await handler(event, data)
