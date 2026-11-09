"""Точка входа. FLEET_BOT_TOKEN, FLEET_OWNER_CHAT_ID, FLEET_DB_URL из окружения."""
import asyncio
import os
from aiogram import Bot, Dispatcher
from db import init_db
from handlers import router
from scheduler import build_scheduler


async def main():
    token = os.environ["FLEET_BOT_TOKEN"]
    owner = int(os.environ["FLEET_OWNER_CHAT_ID"])
    init_db()
    bot = Bot(token)
    dp = Dispatcher()
    dp.include_router(router)
    sch = build_scheduler(bot, owner)
    sch.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
