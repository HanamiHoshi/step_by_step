# handlers/stats.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from database.db import get_user_stats
import os
from utils.image_gen import generate_stats_image

router = Router()

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Показывает текстовую статистику + кнопку для картинки"""
    user_id = message.from_user.id
    stats = await get_user_stats(user_id)

    text = "📊 *Твоя статистика за сегодня:*\n\n"
    text += f"Всего привычек: {stats['total_habits']}\n"
    text += f"✅ Выполнено сегодня: {stats['done_today']}\n"
    text += f"❌ Пропущено сегодня: {stats['skipped_today']}\n\n"

    if stats['best_streak']['name']:
        text += f"🔥 Лучшая цепочка: {stats['best_streak']['value']} дней — *«{stats['best_streak']['name']}»*\n"

    if stats['current_streak']['name']:
        streak = stats['current_streak']['value']
        emoji = "🟢" if streak > 0 else "🔴"
        text += f"{emoji} Текущая цепочка: {streak} дней — *«{stats['current_streak']['name']}»*\n"

    text += "\n💪 Продолжай в том же духе — каждый шаг имеет значение!"
    text += "\n\n🐢 *С уважением, Черепашка Степа* — твой спутник на пути к лучшей версии себя!"

    # Кнопка для показа картинки
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼️ Показать как картинку", callback_data="show_stats_image")]
    ])

    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

@router.message(Command("statsimg"))
async def cmd_statsimg(message: Message):
    """Отправляет статистику в виде картинки"""
    user_id = message.from_user.id

    try:
        # Генерируем картинку
        image_path = await generate_stats_image(user_id)

        # Отправляем
        photo = FSInputFile(image_path)
        await message.answer_photo(
            photo,
            caption="📊 Вот твоя статистика в картинке!\n\n"
                    "Сохрани или поделись с другом — чтобы вдохновлять и вдохновляться 😊"
        )

        # Удаляем временный файл
        if os.path.exists(image_path):
            os.remove(image_path)

    except Exception as e:
        await message.answer("❌ Не удалось сгенерировать картинку. Попробуй позже.")
        print(f"[ERROR] Ошибка генерации изображения: {e}")

@router.callback_query(F.data == "show_stats_image")
async def show_stats_image(callback: CallbackQuery):
    """Обработчик кнопки 'Показать как картинку'"""
    print("✅ [DEBUG] Обработчик show_stats_image сработал!")  # для отладки
    user_id = callback.from_user.id

    try:
        image_path = await generate_stats_image(user_id)
        photo = FSInputFile(image_path)
        await callback.message.answer_photo(
            photo,
            caption="📊 Вот твоя статистика в картинке!"
        )

        # Удаляем файл
        if os.path.exists(image_path):
            os.remove(image_path)

    except Exception as e:
        await callback.message.answer("❌ Не удалось сгенерировать картинку.")
        print(f"[ERROR] {e}")

    # Отвечаем на callback, чтобы убрать "часики" на кнопке
    await callback.answer()