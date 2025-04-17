from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_all_users, get_sessions_count_today
import logging
import asyncio

scheduler = AsyncIOScheduler()
active_sessions = set()
muted_users = set()  # юзеры, которым не нужно ничего присылать


# ⏱ Повторяющееся напоминание при незавершённой сессии
async def start_session_timer(user_id: int, bot: Bot, storage: BaseStorage):
    active_sessions.add(user_id)

    while True:
        print(f"[TIMER] Ждём 30 минут для user_id={user_id}")
        await asyncio.sleep(1800)  # 30 минут

        if user_id not in active_sessions:
            print(f"[TIMER] Сессия завершена для user_id={user_id}, таймер остановлен.")
            break

        if user_id in muted_users:
            print(f"[TIMER] user_id={user_id} отключил уведомления.")
            break

        key = StorageKey(bot_id=bot.id, user_id=user_id, chat_id=user_id)
        data = await storage.get_data(key)
        current_state = data.get("state")
        print(f"[TIMER] Напоминание для user_id={user_id}, state={current_state}")

        await bot.send_message(
            user_id,
            "⏰ Похоже, ты не закончил запись. Давай продолжим?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="▶️ Продолжить", callback_data="resume_session")]
            ])
        )


# Старт таймера для конкретного пользователя
async def register_session_timer(user_id: int, bot: Bot, storage: BaseStorage):
    asyncio.create_task(start_session_timer(user_id, bot, storage))


# ✅ Завершение сессии
def mark_session_complete(user_id: int):
    active_sessions.discard(user_id)

    # Напоминания 3 раза в день, если записей < 3 (чтобы вернуть — убери решетки ниже)
    #
    # async def send_reminder(bot: Bot):
    #     users = await get_all_users()
    #     for user_id in users:
    #         if user_id in muted_users:
    #             logging.info(f"[REMINDER] user_id={user_id} отключил уведомления.")
    #             continue
    #
    #         session_count = await get_sessions_count_today(user_id)
    #
    #         if session_count == 0:
    #             text = "сегодня у тебя ещё нет ни одной записи"
    #         elif session_count == 1:
    #             text = "сегодня у тебя только 1 запись"
    #         elif session_count == 2:
    #             text = "сегодня у тебя только 2 записи"
    #         else:
    #             logging.info(f"[REMINDER] ✅ user_id={user_id} — {session_count} записей, не беспокоим")
    #             continue
    #
    #         await bot.send_message(
    #             user_id,
    #             f"🔔 Напоминание: {text}. Нужно минимум 3. Заполним журнал? 🥺",
    #             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
    #                 [InlineKeyboardButton(text="🔄 Начать новую запись", callback_data="new_entry")]
    #             ])
    #         )


# 🚀 Запуск планировщика (чтобы вернуть 12:00, 16:00, 20:00 — убери решетки ниже)
#
# def start_scheduler(bot: Bot, dp: Dispatcher):
#     scheduler.add_job(
#         send_reminder,
#         trigger=CronTrigger(hour="12,16,20"),
#         args=[bot],
#         id="daily_reminders"
#     )
#     scheduler.start()

async def send_reminder(bot: Bot):
    users = await get_all_users()
    for user_id in users:
        if user_id in muted_users:
            logging.info(f"[REMINDER] user_id={user_id} отключил уведомления.")
            continue
        await bot.send_message(
            user_id,
            "🔔 Напоминание: пора заполнить журнал 📝❤️",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Начать новую запись", callback_data="new_entry")]
            ])
        )


# Запуск планировщика
def start_scheduler(bot: Bot, dp: Dispatcher):
    scheduler.add_job(
        send_reminder,
        trigger=CronTrigger(hour="9-20", minute=0),
        args=[bot],
        id="daily_reminders",
        misfire_grace_time=60
    )
    scheduler.start()
