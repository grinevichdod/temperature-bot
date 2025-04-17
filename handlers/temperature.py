# handlers/temperature.py
# FSM-логика после выбора кофейни: устройства → температуры → имя → завершение

import re
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from session_states import SessionState
from datetime import datetime
from database import save_temperature_entries
from scheduler import mark_session_complete

router = Router()


# Кнопки выбора типа устройства
def device_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧊 Холодильник", callback_data="type:fridge")],
        [InlineKeyboardButton(text="❄️ Морозилка", callback_data="type:freezer")]
    ])


# Кнопки Да / Нет
def yes_no_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="add_more"),
            InlineKeyboardButton(text="❌ Нет", callback_data="finish_devices")
        ]
    ])


# Команда /start повторно
@router.message(F.text == "/start")
async def cmd_start_with_reminder(message: Message, state: FSMContext):
    data = await state.get_data()
    selected = data.get("coffee_code")

    if selected:
        await message.answer(
            f"📍 Ты заполняешь журнал для: {selected}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁 Изменить кофейню", callback_data="restart")]
            ])
        )
        await message.answer("Выберите тип устройства:", reply_markup=device_type_kb())
        await state.set_state(SessionState.choosing_device_type)
    else:
        from handlers.start import generate_coffee_keyboard
        await message.answer("Привет! Выбери свою кофейню:", reply_markup=generate_coffee_keyboard(0))
        await state.set_state(SessionState.start)


# Выбор типа устройства → переход к вводу температуры
@router.callback_query(F.data.startswith("type:"))
async def choose_device_type(callback: CallbackQuery, state: FSMContext):
    device_type = callback.data.split(":")[1]
    await state.update_data(current_type=device_type)
    await callback.message.answer("Введи температуру устройства (используй только цифры и точки):")
    await state.set_state(SessionState.entering_temperature)
    await callback.answer()


# Ввод температуры
@router.message(SessionState.entering_temperature)
async def get_temperature(message: Message, state: FSMContext):
    text = re.sub(r"(?<=[\-+])\s+", "", message.text.replace(",", ".").strip())
    try:
        temp = float(text)
    except ValueError:
        await message.answer("❗ Пожалуйста, введи температуру числом. Например: 4.3 или -18")
        return

    data = await state.get_data()
    device_type = data.get("current_type")

    if not device_type:
        await message.answer("⚠️ Сначала выбери тип устройства.")
        await state.set_state(SessionState.choosing_device_type)
        return

    entries = data.get("entries", [])
    fridge_count = data.get("fridge_count", 0)
    freezer_count = data.get("freezer_count", 0)

    if device_type == "fridge":
        fridge_count += 1
        number = fridge_count
    else:
        freezer_count += 1
        number = freezer_count

    entries.append({
        "type": device_type,
        "number": number,
        "temp": temp
    })

    await state.update_data(
        entries=entries,
        fridge_count=fridge_count,
        freezer_count=freezer_count,
        current_type=None
    )

    total = fridge_count + freezer_count
    if total < 3:
        await message.answer("Добавим ещё устройство 🥶", reply_markup=device_type_kb())
        await state.set_state(SessionState.choosing_device_type)
    else:
        await message.answer("Хочешь добавить ещё устройство?", reply_markup=yes_no_kb())
        await state.set_state(SessionState.confirming_continue)


# Кнопка "Да, добавить ещё"
@router.callback_query(F.data == "add_more")
async def add_more_devices(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Выбери тип устройства:", reply_markup=device_type_kb())
    await state.set_state(SessionState.choosing_device_type)
    await callback.answer()


# Кнопка "Нет, перейти к имени"
@router.callback_query(F.data == "finish_devices")
async def proceed_to_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введи свои имя и фамилию (через пробел):")
    await state.set_state(SessionState.entering_name)
    await callback.answer()


# Ввод имени бариста
@router.message(SessionState.entering_name)
async def handle_name(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("❗ Пожалуйста, введи имя и фамилию через пробел.")
        return

    name = f"{parts[0]} {parts[1]}"
    await state.update_data(barista_name=name)

    data = await state.get_data()
    coffee_code = data.get("coffee_code")

    if not coffee_code:
        await message.answer("⚠️ Ошибка: не удалось получить код кофейни. Попробуй начать заново с /start")
        await state.clear()
        return

    coffee_code = coffee_code.replace("Москва ", "")
    entries = data.get("entries", [])
    barista_name = data.get("barista_name")
    user_id = message.from_user.id

    now = datetime.now()
    session_date = now.date()
    session_time = now.time().replace(microsecond=0)

    await save_temperature_entries(
        user_id=user_id,
        barista_name=barista_name,
        coffee_code=coffee_code,
        entries=entries,
        session_date=session_date,
        session_time=session_time
    )

    mark_session_complete(user_id)

    await message.answer("✅ Спасибо! Данные записаны.\nХорошей смены ☕️",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="🔄 Начать новую запись", callback_data="new_entry")]
                         ]))
    await state.clear()


# Обработчик кнопки "Продолжить" после напоминания
@router.callback_query(F.data == "resume_session")
async def resume_session(callback: CallbackQuery, state: FSMContext):
    current = await state.get_state()

    if current == SessionState.choosing_device_type.state:
        await callback.message.answer("Выбери тип устройства:", reply_markup=device_type_kb())
    elif current == SessionState.entering_temperature.state:
        await callback.message.answer("Введи температуру устройства:")
    elif current == SessionState.entering_name.state:
        await callback.message.answer("Введи имя и фамилию (через пробел):")
    elif current == SessionState.confirming_continue.state:
        await callback.message.answer("Хочешь добавить ещё устройство?", reply_markup=yes_no_kb())
    else:
        await callback.message.answer("Продолжим с того места, где мы остановились.")

    await callback.answer()
