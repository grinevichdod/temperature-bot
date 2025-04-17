# session_states.py
# Определение FSM-состояний для пошагового диалога

from aiogram.fsm.state import StatesGroup, State

class SessionState(StatesGroup):
    # Старт: выбор кофейни
    start = State()

    # Цикл: выбор устройства (холодильник / морозилка)
    choosing_device_type = State()

    # Ввод температуры устройства
    entering_temperature = State()

    # Подтверждение: добавить ещё или закончить
    confirming_continue = State()

    # Ввод имени и фамилии бариста (завершает сессию автоматически)
    entering_name = State()

    # Состояние ожидания (например, после напоминания)
    awaiting_resume_confirmation = State()
