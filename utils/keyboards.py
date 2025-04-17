# utils/keyboards.py
# Общие инлайн-клавиатуры для бота

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def device_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧊 Холодильник", callback_data="type:fridge")],
        [InlineKeyboardButton(text="❄️ Морозилка", callback_data="type:freezer")]
    ])

def yes_no_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="add_more"),
            InlineKeyboardButton(text="❌ Нет", callback_data="finish_devices")
        ]
    ])
