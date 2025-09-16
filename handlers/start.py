# handlers/start.py
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from .habits import cmd_add_habit, cmd_today
from .stats import cmd_stats

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Приветственное сообщение с меню"""
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Помощь"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="➕ Добавить привычку"), KeyboardButton(text="✅ Отметить сегодня")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "👋 Привет! Я — *Шаг за шагом* — твой помощник в построении полезных привычек.\n\n"
        "📌 Начни с команды /add — добавь первую привычку.\n"
        "✅ Каждый день отмечай выполнение — и я помогу тебе не сбиться с пути!\n\n"
        "*Маленькие шаги — большие перемены.* 🚶‍♂️",
        parse_mode="Markdown",
        reply_markup=kb
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Показывает список всех команд с описанием"""
    help_text = (
        "🐢 *Привет! Я — Черепашка Степа, твой помощник в построении привычек.*\n\n"
        "Вот что я умею:\n\n"
        "🔹 *Добавление и управление:*\n"
        "`/add` — добавить новую привычку\n"
        "`/list` — показать все привычки с ID\n"
        "`/edit ID новое название` — переименовать привычку\n"
        "`/delete ID` — удалить привычку (с подтверждением)\n\n"
        "🔹 *Ежедневная практика:*\n"
        "`/today` — отметить выполнение привычек\n"
        "`/remindme ЧЧ:ММ` — установить время напоминаний (например, `/remindme 19:30`)\n"
        "`/remindme off` — отключить напоминания\n\n"
        "🔹 *Статистика и прогресс:*\n"
        "`/stats` — показать твою статистику и цепочки\n"
        "`/statsimg` — получить статистику в виде картинки 🖼️\n"
        "`/resetstats` — сбросить только статистику (историю выполнения), привычки останутся\n\n"
        "🔹 *Полный сброс:*\n"
        "`/reset` — удалить ВСЕ привычки и статистику (с подтверждением) 🗑️\n\n"
        "🔹 *Помощь и навигация:*\n"
        "`/help` — показать это меню снова\n"
        "`/start` — вернуться в начало\n\n"
        "💡 *Совет от Степы:*\n"
        "Не бойся начинать заново — даже черепашки иногда делают шаг назад, чтобы потом прыгнуть вперёд! 🐢\n\n"
        "Начни с `/add` — и я помогу тебе не сбиться с пути!"
    )

    await message.answer(help_text, parse_mode="Markdown")

# Обработчики кнопок
@router.message(F.text == "📚 Помощь")
async def btn_help(message: Message):
    await cmd_help(message)

@router.message(F.text == "📊 Статистика")
async def btn_stats(message: Message):
    await cmd_stats(message)

@router.message(F.text == "➕ Добавить привычку")
async def btn_add(message: Message):
    # Упрощённый вызов — без FSM, просто перенаправляем на /add
    # Можно улучшить позже, если нужно
    await message.answer("📝 Введи название новой привычки:")
    # В идеале — запустить FSM, но для MVP — просто подсказка
    # Полноценный FSM лучше вызывать через команду /add

@router.message(F.text == "✅ Отметить сегодня")
async def btn_today(message: Message):
    await cmd_today(message)