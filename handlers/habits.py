from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,    # ← ДОБАВЬ ЭТУ СТРОКУ
    InlineKeyboardButton     # ← И ЭТУ (если ещё нет)
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from keyboards.inline_kb import get_habit_action_buttons
from database.db import (
    DB_PATH,
    mark_habit_done,
    get_habit_streak,
    add_habit,
    set_user_reminder_time,
    update_habit_name,
    delete_habit,
    get_user_habits,
    reset_user_data,
    reset_user_stats_only,  # ← ЭТА СТРОКА ДОЛЖНА БЫТЬ
)
import aiosqlite
from datetime import date, datetime
from aiogram.exceptions import TelegramBadRequest


router = Router()

class HabitStates(StatesGroup):
    waiting_for_habit_name = State()

@router.message(Command("add"))
async def cmd_add_habit(message: Message, state: FSMContext):
    await message.answer("📝 Введи название новой привычки, которую хочешь развивать:\n\n*Например: «Пить 2 литра воды», «Читать 10 страниц», «Прогулка 30 мин»*", parse_mode="Markdown")
    await state.set_state(HabitStates.waiting_for_habit_name)

# handlers/habits.py

...

@router.message(HabitStates.waiting_for_habit_name)
async def habit_name_entered(message: Message, state: FSMContext):
    habit_name = message.text.strip()

    if len(habit_name) < 2:
        await message.answer("❌ Название слишком короткое. Попробуй ещё раз:")
        return

    if len(habit_name) > 100:
        await message.answer("❌ Название слишком длинное (макс. 100 символов). Попробуй сократить:")
        return

    # Сохраняем (или получаем существующую)
    habit_id = await add_habit(message.from_user.id, habit_name)

    if habit_id:
        # 🔥 Проверяем, новая это привычка или существующая
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT created_at FROM habits WHERE habit_id = ?",
                (habit_id,)
            )
            row = await cursor.fetchone()
            is_new = row and row[0]  # если есть created_at — значит, только что создали

        if is_new:
            response_text = (
                f"✅ Отлично! Привычка *«{habit_name}»* добавлена (ID: {habit_id}).\n\n"
                "Каждый день нажимай «✅ Сделал» — и я буду считать твою цепочку!"
            )
        else:
            response_text = (
                f"🔁 Привычка *«{habit_name}»* уже есть в твоём списке (ID: {habit_id}).\n\n"
                "Просто отметь выполнение через кнопки ниже 👇"
            )

        await message.answer(
            response_text,
            parse_mode="Markdown",
            reply_markup=get_habit_action_buttons()
        )
    else:
        await message.answer("❌ Что-то пошло не так при сохранении. Попробуй ещё раз.")

    await state.clear()
# Обработчик кнопки "✅ Сделал сегодня"
@router.callback_query(F.data == "habit_done")
async def habit_done(callback: CallbackQuery):
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT habit_id, name FROM habits WHERE user_id = ? ORDER BY habit_id DESC LIMIT 1",
            (user_id,)
        )
        row = await cursor.fetchone()

    if not row:
        await callback.answer("❌ У тебя ещё нет привычек. Добавь через /add", show_alert=True)
        return

    habit_id, habit_name = row

    # 🔥 Проверяем, не отмечено ли уже сегодня
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT done FROM habit_logs WHERE habit_id = ? AND date = ?",
            (habit_id, today)
        )
        existing = await cursor.fetchone()

    if existing:
        done_status = "сделано" if existing[0] else "пропущено"
        await callback.answer(f"ℹ️ Ты уже отметил это как '{done_status}' сегодня", show_alert=True)
        return  # НЕ редактируем сообщение — выходим

    # Если не отмечено — сохраняем
    await mark_habit_done(habit_id, done=True)
    streak = await get_habit_streak(habit_id)

    message_text = f"✅ Отлично! Ты сделал привычку *«{habit_name}»* сегодня!\n\n🔥 Цепочка: {streak} дней подряд"

    if streak == 3:
        message_text += "\n\n🥉 Ура! 3 дня подряд — ты в начале пути!"
    elif streak == 7:
        message_text += "\n\n🥈 7 дней! Ты как робот-трудяга! 🤖"
    elif streak == 30:
        message_text += "\n\n🥇 30 ДНЕЙ! Ты легенда! Это уже часть твоей жизни! 🎉"

    try:
        await callback.message.edit_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=get_habit_action_buttons()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # На всякий случай — отправим как новое сообщение
            await callback.message.answer(message_text, parse_mode="Markdown", reply_markup=get_habit_action_buttons())
        else:
            raise

    await callback.answer()
# Обработчик кнопки "❌ Пропустил"
@router.callback_query(F.data == "habit_skip")
async def habit_skip(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Получаем последнюю привычку пользователя
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT habit_id, name FROM habits WHERE user_id = ? ORDER BY habit_id DESC LIMIT 1",
            (user_id,)
        )
        row = await cursor.fetchone()

    if not row:
        await callback.answer("❌ У тебя ещё нет привычек. Добавь через /add", show_alert=True)
        return

    habit_id, habit_name = row

    # 🔥 Проверяем, не отмечено ли уже сегодня
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT done FROM habit_logs WHERE habit_id = ? AND date = ?",
            (habit_id, today)
        )
        existing = await cursor.fetchone()

    if existing:
        done_status = "сделано ✅" if existing[0] else "пропущено ❌"
        await callback.answer(f"ℹ️ Ты уже отметил «{habit_name}» как {done_status} сегодня", show_alert=True)
        return  # Не обновляем сообщение — выходим

    # Если не отмечено — сохраняем как "не сделано"
    await mark_habit_done(habit_id, done=False)

    message_text = f"❌ Ты пропустил привычку *«{habit_name}»* сегодня.\nНе переживай — завтра новый шанс! 🌱"

    try:
        await callback.message.edit_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=get_habit_action_buttons()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # На всякий случай — отправим как новое сообщение
            await callback.message.answer(message_text, parse_mode="Markdown", reply_markup=get_habit_action_buttons())
        else:
            raise  # если другая ошибка — пробрасываем

    await callback.answer()  # убираем "часики" с кнопки
@router.message(Command("today"))
async def cmd_today(message: Message):
    user_id = message.from_user.id

    # Получаем список привычек пользователя
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT habit_id, name FROM habits WHERE user_id = ?",
            (user_id,)
        )
        habits_list = await cursor.fetchall()

    if not habits_list:
        await message.answer("📝 У тебя ещё нет привычек. Добавь первую через /add")
        return

    # Формируем сообщение со списком
    text = "📋 Твои привычки:\n\n"
    for habit_id, name in habits_list:
        text += f"🔹 {name} (ID: {habit_id})\n"

    text += "\n👉 Нажми на кнопку под сообщением, чтобы отметить выполнение."

    # Создаём кнопки для каждой привычки
    buttons = []
    for habit_id, name in habits_list:
        buttons.append([
            InlineKeyboardButton(text=f"✅ {name}", callback_data=f"done_{habit_id}"),
            InlineKeyboardButton(text=f"❌ {name}", callback_data=f"skip_{habit_id}")
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, reply_markup=keyboard)
@router.callback_query(F.data.startswith("done_"))
async def today_done(callback: CallbackQuery):
    habit_id = int(callback.data.split("_")[1])
    await mark_habit_done(habit_id, done=True)

    # Получаем название привычки
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name FROM habits WHERE habit_id = ?", (habit_id,))
        row = await cursor.fetchone()

    if not row:
        await callback.answer("❌ Привычка не найдена", show_alert=True)
        return

    habit_name = row[0]
    streak = await get_habit_streak(habit_id)

    message_text = f"✅ Ты сделал «{habit_name}» сегодня!\n🔥 Цепочка: {streak} дней"

    if streak == 3:
        message_text += "\n\n🥉 3 дня! Ты в начале пути!"
    elif streak == 7:
        message_text += "\n\n🥈 7 дней! Ты — машина!"
    elif streak == 30:
        message_text += "\n\n🥇 30 ДНЕЙ! Ты легенда!"

    await callback.message.edit_text(message_text)
    await callback.answer()

@router.callback_query(F.data.startswith("skip_"))
async def today_skip(callback: CallbackQuery):
    habit_id = int(callback.data.split("_")[1])
    await mark_habit_done(habit_id, done=False)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name FROM habits WHERE habit_id = ?", (habit_id,))
        row = await cursor.fetchone()

    if not row:
        await callback.answer("❌ Привычка не найдена", show_alert=True)
        return

    habit_name = row[0]
    await callback.message.edit_text(f"❌ Ты пропустил «{habit_name}» сегодня. Завтра новый шанс!")
    await callback.answer()
@router.message(Command("remindme"))
async def cmd_remindme(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "⏰ Укажи время для ежедневных напоминаний в формате ЧЧ:ММ\n"
            "Например: `/remindme 19:30`\n\n"
            "Чтобы отключить — `/remindme off`",
            parse_mode="Markdown"
        )
        return

    time_str = args[1].strip()

    if time_str.lower() == "off":
        await set_user_reminder_time(message.from_user.id, None)
        await message.answer("🔕 Напоминания отключены. Возвращайся, когда захочешь — я всегда рядом 🐢")
        return

    # Проверяем формат времени
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используй ЧЧ:ММ, например: 19:30")
        return

    await set_user_reminder_time(message.from_user.id, time_str)
    await message.answer(
        f"✅ Отлично! Теперь я буду напоминать тебе каждый день в *{time_str}*.\n\n"
        "🌿 Черепашка Степа позаботится, чтобы ты ничего не забыл!",
        parse_mode="Markdown"
    )
@router.message(Command("testreminder"))
async def cmd_test_reminder(message: Message):
    """Тестовая команда — отправляет напоминание СЕЙЧАС"""
    user_id = message.from_user.id
    from utils.scheduler import send_daily_reminder
    from aiogram import Bot

    # Получаем бота из контекста (костыль для теста)
    bot = message.bot

    await send_daily_reminder(bot, user_id)
    await message.answer("📬 Тестовое напоминание отправлено!")
@router.message(Command("list"))
async def cmd_list_habits(message: Message):
    """Показывает список всех привычек пользователя с ID"""
    user_id = message.from_user.id

    # Получаем привычки
    habits = await get_user_habits(user_id)  # эта функция уже есть в db.py

    if not habits:
        await message.answer("📝 У тебя ещё нет привычек. Добавь первую через /add")
        return

    text = "📋 *Твои привычки:*\n\n"
    for habit_id, name in habits:
        text += f"🔹 ID {habit_id}: *{name}*\n"

    text += "\n✏️ Чтобы изменить — `/edit ID новое название`\n🗑️ Чтобы удалить — `/delete ID`"

    await message.answer(text, parse_mode="Markdown")
async def update_habit_name(habit_id: int, new_name: str) -> bool:
    """Обновляет название привычки. Возвращает True, если успешно."""
    if len(new_name.strip()) < 2:
        return False
    if len(new_name) > 100:
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE habits SET name = ? WHERE habit_id = ?",
            (new_name.strip(), habit_id)
        )
        await db.commit()

        cursor = await db.execute("SELECT changes()")
        changes = await cursor.fetchone()
        return changes[0] > 0  # если 0 — значит, не было такой привычки
@router.message(Command("edit"))
async def cmd_edit_habit(message: Message):
    """Редактирует название привычки: /edit <ID> <новое название>"""
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer(
            "✏️ Используй формат: `/edit ID новое название`\n"
            "Например: `/edit 1 Пить 3 литра воды`\n\n"
            "Узнать ID: /list",
            parse_mode="Markdown"
        )
        return

    try:
        habit_id = int(args[1])
        new_name = args[2].strip()
    except ValueError:
        await message.answer("❌ ID должен быть числом. Проверь команду.")
        return

    # Проверяем, существует ли привычка и принадлежит ли пользователю
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT h.habit_id FROM habits h JOIN users u ON h.user_id = u.user_id WHERE h.habit_id = ? AND u.user_id = ?",
            (habit_id, message.from_user.id)
        )
        row = await cursor.fetchone()

    if not row:
        await message.answer("❌ Привычка с таким ID не найдена или не принадлежит тебе.")
        return

    # Обновляем название
    success = await update_habit_name(habit_id, new_name)

    if success:
        await message.answer(
            f"✅ Готово! Привычка теперь называется:\n*«{new_name}»*\n\n"
            "🌿 Черепашка Степа одобряет! Теперь отмечай с удовольствием 😊",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Не удалось обновить название. Убедись, что оно от 2 до 100 символов.")
pending_deletions = set()

@router.message(Command("delete"))
async def cmd_delete_habit(message: Message):
    """Запрашивает подтверждение удаления привычки"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "🗑️ Используй формат: `/delete ID`\n"
            "Например: `/delete 1`\n\n"
            "Узнать ID: /list",
            parse_mode="Markdown"
        )
        return

    try:
        habit_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return

    # Проверяем, существует ли привычка и принадлежит ли пользователю
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT name FROM habits WHERE habit_id = ? AND user_id = ?",
            (habit_id, message.from_user.id)
        )
        row = await cursor.fetchone()

    if not row:
        await message.answer("❌ Привычка с таким ID не найдена или не принадлежит тебе.")
        return

    habit_name = row[0]
    pending_deletions.add(habit_id)

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{habit_id}"),
            InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_delete")
        ]
    ])

    await message.answer(
        f"⚠️ Ты уверен, что хочешь удалить привычку *«{habit_name}»*?\n"
        "Это действие нельзя отменить — все данные о выполнении будут удалены.",
        parse_mode="Markdown",
        reply_markup=confirm_kb
    )

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete(callback: CallbackQuery):
    habit_id = int(callback.data.split("_")[2])

    if habit_id not in pending_deletions:
        await callback.answer("❌ Запрос устарел. Попробуй снова через /delete", show_alert=True)
        return

    success = await delete_habit(habit_id, callback.from_user.id)

    if success:
        await callback.message.edit_text(
            f"🗑️ Привычка удалена.\n\n"
            "🌿 Степа говорит: «Иногда нужно отпускать, чтобы расти дальше» 🐢"
        )
    else:
        await callback.message.edit_text("❌ Не удалось удалить привычку. Попробуй позже.")

    pending_deletions.discard(habit_id)
    await callback.answer()

@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("✅ Удаление отменено. Привычка сохранена!")
    await callback.answer()
pending_resets = set()

@router.message(Command("reset"))
async def cmd_reset(message: Message):
    """Запрашивает подтверждение на полный сброс данных"""
    pending_resets.add(message.from_user.id)

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, сбросить всё", callback_data="confirm_reset"),
            InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_reset")
        ]
    ])

    await message.answer(
        "⚠️ *Ты уверен, что хочешь полностью сбросить все привычки и статистику?*\n\n"
        "Это действие:\n"
        "• Удалит все твои привычки\n"
        "• Сбросит все цепочки и логи\n"
        "• Нельзя отменить\n\n"
        "Ты начнёшь с чистого листа — как будто в первый раз! 🌱",
        parse_mode="Markdown",
        reply_markup=confirm_kb
    )

@router.callback_query(F.data == "confirm_reset")
async def confirm_reset(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in pending_resets:
        await callback.answer("❌ Запрос устарел. Попробуй снова через /reset", show_alert=True)
        return

    success = await reset_user_data(user_id)

    if success:
        await callback.message.edit_text(
            "✅ *Готово!* Все привычки и статистика удалены.\n\n"
            "🌿 Черепашка Степа говорит: «Новый старт — это шанс стать ещё лучше!» 🐢\n"
            "Начни заново с команды /add — я с тобой!",
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            "❌ Не удалось сбросить данные. Возможно, у тебя ещё не было привычек.",
            parse_mode="Markdown"
        )

    pending_resets.discard(user_id)
    await callback.answer()

@router.callback_query(F.data == "cancel_reset")
async def cancel_reset(callback: CallbackQuery):
    await callback.message.edit_text(
        "😌 Отменено. Твои привычки в безопасности!\n"
        "Ты всегда можешь сбросить позже — я напомню 😉",
        parse_mode="Markdown"
    )
    await callback.answer()
# Для подтверждения сброса
pending_resets = set()

@router.message(Command("reset"))
async def cmd_reset(message: Message):
    """Запрашивает подтверждение на полный сброс данных"""
    pending_resets.add(message.from_user.id)

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, сбросить всё", callback_data="confirm_reset"),
            InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_reset")
        ]
    ])

    await message.answer(
        "⚠️ *Ты уверен, что хочешь полностью сбросить все привычки и статистику?*\n\n"
        "Это действие:\n"
        "• Удалит все твои привычки\n"
        "• Сбросит все цепочки и логи\n"
        "• Нельзя отменить\n\n"
        "Ты начнёшь с чистого листа — как будто в первый раз! 🌱",
        parse_mode="Markdown",
        reply_markup=confirm_kb
    )

@router.callback_query(F.data == "confirm_reset")
async def confirm_reset(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in pending_resets:
        await callback.answer("❌ Запрос устарел. Попробуй снова через /reset", show_alert=True)
        return

    success = await reset_user_data(user_id)

    if success:
        await callback.message.edit_text(
            "✅ *Готово!* Все привычки и статистика удалены.\n\n"
            "🌿 Черепашка Степа говорит: «Новый старт — это шанс стать ещё лучше!» 🐢\n"
            "Начни заново с команды /add — я с тобой!",
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            "❌ Не удалось сбросить данные. Возможно, у тебя ещё не было привычек.",
            parse_mode="Markdown"
        )

    pending_resets.discard(user_id)
    await callback.answer()

@router.callback_query(F.data == "cancel_reset")
async def cancel_reset(callback: CallbackQuery):
    await callback.message.edit_text(
        "😌 Отменено. Твои привычки в безопасности!\n"
        "Ты всегда можешь сбросить позже — я напомню 😉",
        parse_mode="Markdown"
    )
    await callback.answer()
@router.message(Command("resetstats"))
async def cmd_resetstats(message: Message):
    """Сбрасывает только статистику (логи), привычки остаются"""
    success = await reset_user_stats_only(message.from_user.id)

    if success:
        await message.answer(
            "📊 *Статистика сброшена!* Твои привычки остались, но история выполнения удалена.\n\n"
            "Теперь ты можешь строить новые цепочки — с чистого листа! 🌱",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Нет данных для сброса.")