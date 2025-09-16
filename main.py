# main.py
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from config.settings import BOT_TOKEN
from database.db import init_db
from handlers import start, habits, stats
from utils.scheduler import scheduler, schedule_daily_reminders

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def main():
    print("📂 [MAIN] Текущая рабочая директория:", os.getcwd())
    print("🐍 [MAIN] Путь к main.py:", os.path.abspath(__file__))

    # 🟢 1. САМОЕ ПЕРВОЕ — инициализация базы данных
    print("⏳ [MAIN] Инициализация базы данных...")
    await init_db()
    print("✅ [MAIN] База данных готова")

    # Запускаем планировщик
    scheduler.start()
    schedule_daily_reminders(bot)
    print("⏰ [MAIN] Планировщик напоминаний запущен")

    # 🟡 2. Подключаем роутеры
    print("🔌 [MAIN] Подключение обработчиков...")
    dp.include_router(start.router)
    dp.include_router(habits.router)
    dp.include_router(stats.router)  # ← добавь эту строку
    print("✅ [MAIN] Обработчики подключены")

    # 🔵 3. Очищаем очередь и запускаем polling
    print("🧹 [MAIN] Очистка старых обновлений...")
    await bot.delete_webhook(drop_pending_updates=True)

    print("🚀 [MAIN] Запуск бота...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()  # корректно завершаем планировщик
        print("🛑 [MAIN] Планировщик остановлен")

if __name__ == "__main__":
    print("🏁 [MAIN] Запуск приложения...")
    asyncio.run(main())