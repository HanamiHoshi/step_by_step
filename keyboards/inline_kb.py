# keyboards/inline_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_habit_action_buttons():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сделал сегодня", callback_data="habit_done"),
            InlineKeyboardButton(text="❌ Пропустил", callback_data="habit_skip")
        ]
    ])