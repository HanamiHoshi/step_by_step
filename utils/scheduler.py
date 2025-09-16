# utils/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
import asyncio
import aiosqlite
from database.db import get_user_reminder_time, get_user_habits, DB_PATH
from datetime import datetime

scheduler = AsyncIOScheduler()

async def send_daily_reminder(bot: Bot, user_id: int):
    """Отправляет ежедневное напоминание пользователю"""
    # Получаем время напоминания
    reminder_time = await get_user_reminder_time(user_id)
    if not reminder_time:
        return  # Нет времени — не напоминаем

    # Получаем список привычек
    habits = await get_user_habits(user_id)
    if not habits:
        return  # Нет привычек — нечего напоминать

    # Формируем сообщение
    habit_names = "\n".join([f"• {name}" for _, name in habits])
    message_text = (
        f"🌿 *Черепашка Степа напоминает:*\n\n"
        f"Не забудь сегодня поработать над своими привычками:\n\n"
        f"{habit_names}\n\n"
        f"Потом отметь через /today или кнопки 😊\n"
        f"Ты молодец — я в тебя верю! 🐢💪"
    )

    try:
        await bot.send_message(user_id, message_text, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ [SCHEDULER] Не удалось отправить напоминание пользователю {user_id}: {e}")

def schedule_daily_reminders(bot: Bot):
    """Планирует ежедневные напоминания для всех пользователей"""
    # Пример: проверяем каждые 60 секунд, не наступило ли время напоминания для кого-то
    async def check_and_send():
        from database.db import init_db  # ленивый импорт, чтобы избежать циклических зависимостей
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id, reminder_time FROM users WHERE reminder_time IS NOT NULL")
            users = await cursor.fetchall()

        now = datetime.now()
        current_time = now.strftime("%H:%M")

        for user_id, reminder_time in users:
            if reminder_time == current_time:
                asyncio.create_task(send_daily_reminder(bot, user_id))

    scheduler.add_job(check_and_send, 'interval', seconds=60, id='reminder_checker')