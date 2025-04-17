# handlers/start.py
# Обработчик команды /start с выбором начать или нет, плюс выбор кофейни с пагинацией

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from session_states import SessionState
from database import save_user_coffee, get_user_coffee
from scheduler import register_session_timer
from scheduler import mark_session_complete, muted_users
from database import remove_from_mute_users, add_to_mute_users


router = Router()

# Список кофеен для выбора
COFFEE_LIST = [
    "Москва 0-1 (Омега Плаза)",
    "Москва 0-10 (Магистраль Плаза)",
    "Москва 0-11 (Симонов Плаза)",
    "Москва 0-12 (Арма)",
    "Москва 0-13 (Смарт Парк)",
    "Москва 0-14 (Верейская Плаза)",
    "Москва 0-15 (Сретенка)",
    "Москва 0-15.1 (Учебный Центр)",
    "Москва 0-16.5 (Т-Банк | 5 этаж)",
    "Москва 0-16.7 (Т-Банк | 7 этаж)",
    "Москва 0-16.9 (Т-Банк | 9 этаж)",
    "Москва 0-17 (Хлебозавод)",
    "Москва 0-18 (Альфа-Банк Паскаль)",
    "Москва 0-19 (Солнце Москвы)",
    "Москва 0-2 (Сити-Федерация)",
    "Москва 0-21.4 (Центральный Университет | 4 этаж)",
    "Москва 0-21.8 (Центральный Университет | 8 этаж)",
    "Москва 0-22 (РИО)",
    "Москва 0-23 (ВЭБ Центр)",
    "Москва 0-24 (Поклонка Плейс Остров)",
    "Москва 0-27 (Альфа-Банк Немецкий центр)",
    "Москва 0-3 (Даймонд Холл)",
    "Москва 0-30 (Афимолл Галерея)"
]

PER_PAGE = 5
callback_on_select = None


def register_callback(callback):
    global callback_on_select
    callback_on_select = callback


# /start — показывает приветствие с кнопками Да/Нет
@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await remove_from_mute_users(message.from_user.id)
    await state.clear()
    await message.answer(
        "Привет! Я помогу тебе заполнить журнал температур.\n"
        "Отправляй сначала температуру холодильников, затем морозилок.\n"
        "Напоминаю: использовать можно только цифры и точки, никаких запятых.\n\n"
        "Начинаем?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="start_session"),
                InlineKeyboardButton(text="❌ Нет", callback_data="cancel_session")
            ]
        ])
    )


@router.callback_query(F.data == "cancel_session")
async def cancel_session(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Увидимся в другой раз! 👋",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Начать новую запись", callback_data="new_entry")]
        ])
    )
    await state.clear()
    await callback.answer()


# Пользователь согласен начать — если кофейня уже есть, сразу переходим
@router.callback_query(F.data == "start_session")
async def start_session(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    muted_users.discard(user_id)  # Убираем из списка отключённых
    coffee_code = await get_user_coffee(user_id)

    if coffee_code:
        await state.update_data(coffee_code=coffee_code)
        from handlers.temperature import device_type_kb
        await callback.message.answer(
            f"📍 Ты заполняешь журнал для: {coffee_code}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁 Изменить кофейню", callback_data="restart")]
            ])
        )
        await callback.message.answer("Выбери тип устройства:", reply_markup=device_type_kb())
        await state.set_state(SessionState.choosing_device_type)
        await register_session_timer(user_id, callback.bot, state.storage)
    else:
        await state.set_state(SessionState.start)
        await callback.message.answer("Из какой ты кофейни?", reply_markup=generate_coffee_keyboard(0))

    await callback.answer()


# Пагинация списка кофеен

def generate_coffee_keyboard(page: int):
    start = page * PER_PAGE
    end = start + PER_PAGE
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"select_index:{i}")]
        for i, name in enumerate(COFFEE_LIST[start:end], start=start)
    ]
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page:{page - 1}"))
    if end < len(COFFEE_LIST):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Далее", callback_data=f"page:{page + 1}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Переключение страниц
@router.callback_query(F.data.startswith("page:"))
async def paginate_coffee_list(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=generate_coffee_keyboard(page))
    await callback.answer()


# Выбор кофейни → переход к температуре
@router.callback_query(F.data.startswith("select_index:"))
async def select_coffee(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split(":")[1])
    selected = COFFEE_LIST[index]
    await state.update_data(coffee_code=selected, entries=[], fridge_count=0, freezer_count=0)
    await save_user_coffee(callback.from_user.id, selected)

    await callback.message.edit_text(
        f"📍 <b>Ты заполняешь журнал для:</b>\n{selected}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Изменить кофейню", callback_data="restart")]
        ])
    )

    from handlers.temperature import device_type_kb
    await callback.message.answer("Выбери тип устройства:", reply_markup=device_type_kb())
    await state.set_state(SessionState.choosing_device_type)

    # await register_session_timer(callback.from_user.id, callback.bot, state.storage)

    if callback_on_select:
        await callback_on_select(callback.from_user.id)

    await callback.answer()


# Повторный запуск — изменение кофейни
@router.callback_query(F.data == "restart")
async def restart_flow(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SessionState.start)
    await callback.message.answer("Выбери свою кофейню:", reply_markup=generate_coffee_keyboard(0))
    await callback.answer()


# Новая запись — начать всё заново, как с /start
@router.callback_query(F.data == "new_entry")
async def new_entry(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    await callback.message.answer(
        "Привет! Я помогу тебе заполнить журнал температур.\n"
        "Отправляй сначала температуру холодильников, затем морозилок.\n"
        "Напоминаю: использовать можно только цифры и точки, никаких запятых.\n\n"
        "Начинаем?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="start_session"),
                InlineKeyboardButton(text="❌ Нет", callback_data="cancel_session")
            ]
        ])
    )

    await callback.answer()


@router.message(F.text == "/stop")
async def stop_notifications(message: Message):
    await add_to_mute_users(message.from_user.id)
    await message.answer("🔕 Уведомления отключены. Чтобы снова получать напоминания — просто нажми /start.")
