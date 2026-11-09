"""Планировщик напоминаний: платёж, еженедельный пробег, ТО, страховка."""
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import SessionLocal
from services import FleetService


def build_scheduler(bot, owner_chat_id: int) -> AsyncIOScheduler:
    sch = AsyncIOScheduler(timezone="Europe/Moscow")

    async def daily_reminders():
        s = FleetService(SessionLocal())
        for ev in s.reminders_due():
            if ev["type"] == "rent_due" and ev["tg_id"]:
                await bot.send_message(ev["tg_id"],
                    f"Напоминание: сегодня день оплаты аренды — {ev['amount']} ₽")
            elif ev["type"] == "to_soon":
                await bot.send_message(owner_chat_id,
                    f"ТО скоро: {ev['car']} — осталось {ev['km_left']} км")
            elif ev["type"] == "insurance":
                await bot.send_message(owner_chat_id,
                    f"Страховка истекает: {ev['car']} — до {ev['until']}")
            elif ev["type"] == "debt":
                await bot.send_message(owner_chat_id,
                    f"Долг: {ev['driver']} — {ev['debt']} ₽")

    async def weekly_mileage_request():
        s = FleetService(SessionLocal())
        from models import Driver, User
        for d in s.s.query(Driver).filter_by(active=True).all():
            u = s.s.get(User, d.user_id)
            await bot.send_message(u.tg_id,
                "Перешлите, пожалуйста, текущий пробег (кнопка «Передать пробег»)")

    sch.add_job(daily_reminders, "cron", hour=9, minute=0)
    sch.add_job(weekly_mileage_request, "cron", day_of_week="mon", hour=10, minute=0)
    return sch
