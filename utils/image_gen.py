# utils/image_gen.py
from PIL import Image, ImageDraw, ImageFont
import os
import re
from database.db import get_user_stats, get_user_habits

# Пути к шрифтам
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
EMOJI_FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "NotoEmoji-Regular.ttf")

def get_font(size=20):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception as e:
        print(f"[WARN] Не удалось загрузить основной шрифт: {e}")
        return ImageFont.load_default()

def get_emoji_font(size=20):
    try:
        return ImageFont.truetype(EMOJI_FONT_PATH, size)
    except Exception as e:
        print(f"[WARN] Не удалось загрузить шрифт эмодзи: {e}")
        return get_font(size)

def is_emoji(char):
    """Проверяет, является ли символ эмодзи"""
    emoji_ranges = [
        (0x1F300, 0x1F6FF),    # Miscellaneous Symbols and Pictographs
        (0x1F900, 0x1F9FF),    # Supplemental Symbols and Pictographs
        (0x2600, 0x26FF),      # Miscellaneous Symbols
        (0x2700, 0x27BF),      # Dingbats
        (0x1F1E6, 0x1F1FF),    # Flags
    ]
    cp = ord(char)
    return any(start <= cp <= end for start, end in emoji_ranges)

def draw_text_with_emoji(draw, text, x, y, font, emoji_font, fill=(0, 0, 0)):
    """Рисует текст, используя разные шрифты для текста и эмодзи. Эмодзи рисуются ЧЁРНЫМ, текст — с fill."""
    for char in text:
        if is_emoji(char):
            # Эмодзи — всегда чёрным (или стандартным цветом шрифта)
            draw.text((x, y), char, font=emoji_font, fill=(0, 0, 0))
        else:
            # Обычный текст — с заданным fill
            draw.text((x, y), char, font=font, fill=fill)
        # Получаем ширину символа
        current_font = emoji_font if is_emoji(char) else font
        bbox = draw.textbbox((0, 0), char, font=current_font)
        x += bbox[2] - bbox[0]  # сдвигаем x

async def generate_stats_image(user_id: int) -> str:
    """Генерирует картинку со статистикой и возвращает путь к файлу"""
    stats = await get_user_stats(user_id)
    habits = await get_user_habits(user_id)

    width, height = 600, 500
    img = Image.new('RGB', (width, height), color=(240, 248, 255))  # aliceblue
    draw = ImageDraw.Draw(img)

    # Шрифты
    title_font = get_font(28)
    text_font = get_font(20)
    emoji_font = get_emoji_font(22)

    # Заголовок
    draw_text_with_emoji(draw, "📊 Твоя статистика", 20, 20, text_font, emoji_font, fill=(40, 40, 40))

    # Основной текст
    y = 80
    draw_text_with_emoji(draw, f"Всего привычек: {stats['total_habits']}", 20, y, text_font, emoji_font, fill=(60, 60, 60))
    y += 40
    draw_text_with_emoji(draw, f"✅ Сегодня: {stats['done_today']}", 20, y, text_font, emoji_font, fill=(30, 180, 30))
    y += 40
    draw_text_with_emoji(draw, f"❌ Пропущено: {stats['skipped_today']}", 20, y, text_font, emoji_font, fill=(180, 30, 30))

    # Лучшая цепочка
    y += 50
    if stats['best_streak']['name']:
        streak = stats['best_streak']['value']
        name = stats['best_streak']['name']
        draw_text_with_emoji(draw, f"🔥 Лучшая цепочка: {streak} дней", 20, y, text_font, emoji_font, fill=(220, 120, 30))
        y += 30
        draw_text_with_emoji(draw, f"«{name}»", 40, y, text_font, emoji_font, fill=(80, 80, 80))

    # Текущая цепочка
    y += 40
    if stats['current_streak']['name']:
        streak = stats['current_streak']['value']
        name = stats['current_streak']['name']
        color = (30, 180, 30) if streak > 0 else (180, 30, 30)
        emoji_char = "🎯" if streak > 0 else "🔄"
        draw_text_with_emoji(draw, f"{emoji_char} Текущая цепочка: {streak} дней", 20, y, text_font, emoji_font, fill=color)
        y += 30
        draw_text_with_emoji(draw, f"«{name}»", 40, y, text_font, emoji_font, fill=(80, 80, 80))

    # Подпись Степы
    y += 50
    draw_text_with_emoji(draw, "🐢 С уважением, Черепашка Степа", 20, y, text_font, emoji_font, fill=(70, 130, 180))
    y += 25
    draw_text_with_emoji(draw, "Ты молодец — я в тебя верю!", 20, y, text_font, emoji_font, fill=(70, 130, 180))

    # Сохраняем
    output_path = f"stats_{user_id}.png"
    img.save(output_path)
    return output_path