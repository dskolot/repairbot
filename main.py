import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from core.config import BOT_TOKEN
from bot.middlewares.auth import AuthMiddleware
from bot.handlers import new_order, orders, finance
from bot.handlers.start import router as start_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware — проверка доступа для каждого сообщения
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Роутеры
    dp.include_router(start_router)
    dp.include_router(new_order.router)
    dp.include_router(orders.router)
    dp.include_router(finance.router)

    logging.info("Бот запущен ✅")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
