import asyncpg
import os
from datetime import date, time
from typing import List
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")  # В .env: DATABASE_URL=postgresql://user:pass@host:port/db

# Асинхронное подключение к БД
async def get_connection():
    return await asyncpg.connect(DB_URL, statement_cache_size=0)

# Сохраняем список записей от одного бариста (одна сессия)
async def save_temperature_entries(
    user_id: int,
    barista_name: str,
    coffee_code: str,
    entries: List[dict],
    session_date: date,
    session_time: time
):
    conn = await get_connection()
    try:
        for entry in entries:
            # Перевод типа устройства на русский
            type_ru = "Холодильник" if entry["type"] == "fridge" else "Морозилка"
            # Удаляем "Москва " из начала строки
            clean_code = coffee_code.replace("Москва ", "")
            # Обрезаем микросекунды у времени
            clean_time = session_time.replace(microsecond=0)

            await conn.execute(
                """
                INSERT INTO temp_journal (
                    user_id, barista, coffeeshop_id,
                    date, time, device_type,
                    device_number, temperature
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                user_id,
                barista_name,
                clean_code,
                session_date,
                clean_time,
                type_ru,
                entry["number"],
                entry["temp"]
            )
    finally:
        await conn.close()

# Сохранить выбранную кофейню пользователя
async def save_user_coffee(user_id: int, coffee_code: str):
    conn = await get_connection()
    await conn.execute("""
        INSERT INTO user_profiles (user_id, coffeeshop_code)
        VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE
        SET coffeeshop_code = EXCLUDED.coffeeshop_code
    """, user_id, coffee_code)
    await conn.close()

# Получить сохранённую кофейню пользователя
async def get_user_coffee(user_id: int) -> str | None:
    conn = await get_connection()
    row = await conn.fetchrow("SELECT coffeeshop_code FROM user_profiles WHERE user_id = $1", user_id)
    await conn.close()
    return row["coffeeshop_code"] if row else None

# Получить количество завершённых сессий (уникальных time) за сегодня
async def get_sessions_count_today(user_id: int) -> int:
    conn = await get_connection()
    try:
        result = await conn.fetchval("""
            SELECT COUNT(DISTINCT time)
            FROM temp_journal
            WHERE user_id = $1 AND date = $2
        """, user_id, date.today())
        return result or 0
    finally:
        await conn.close()

# Получить всех пользователей, у кого были записи
async def get_all_users() -> list[int]:
    conn = await get_connection()
    try:
        rows = await conn.fetch("SELECT DISTINCT user_id FROM temp_journal")
        return [row["user_id"] for row in rows]
    finally:
        await conn.close()

# Добавить пользователя в mute_users
async def add_to_mute_users(user_id: int):
    conn = await get_connection()
    await conn.execute("""
        INSERT INTO mute_users (user_id)
        VALUES ($1)
        ON CONFLICT (user_id) DO NOTHING
    """, user_id)
    await conn.close()


# Удалить пользователя из mute_users
async def remove_from_mute_users(user_id: int):
    conn = await get_connection()
    await conn.execute("DELETE FROM mute_users WHERE user_id = $1", user_id)
    await conn.close()

