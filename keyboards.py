"""Клавиатуры владельца и водителя."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

OWNER_KB = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🚗 Автомобили"), KeyboardButton(text="👷 Водители")],
    [KeyboardButton(text="💰 Платежи на проверке"), KeyboardButton(text="📊 Статистика")],
    [KeyboardButton(text="🔧 Неисправности")],
], resize_keyboard=True)

DRIVER_KB = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="💳 Моя аренда"), KeyboardButton(text="📤 Отправить оплату")],
    [KeyboardButton(text="🛣 Передать пробег"), KeyboardButton(text="🔧 Сообщить о неисправности")],
], resize_keyboard=True)

def confirm_payment_kb(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"pay_ok:{payment_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"pay_no:{payment_id}"),
    ]])
