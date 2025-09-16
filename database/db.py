# database/db.py
import aiosqlite
import os
from datetime import date

# Определяем путь до корня проекта и файл БД
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "habits.db")

async def init_db():
    """Создаёт все таблицы, если их ещё нет + обновляет структуру при необходимости"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        """)
        print("✅ [DB] Таблица 'users' создана или уже существует")

        # Добавляем столбец reminder_time, если его нет
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "reminder_time" not in column_names:
            await db.execute("ALTER TABLE users ADD COLUMN reminder_time TEXT DEFAULT NULL")
            print("➕ [DB] Добавлен столбец 'reminder_time' в таблицу 'users'")

        # Таблица привычек
        await db.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                habit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        print("✅ [DB] Таблица 'habits' создана или уже существует")

        # Таблица логов выполнения
        await db.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                date TEXT NOT NULL,  -- формат YYYY-MM-DD
                done BOOLEAN DEFAULT 1,
                FOREIGN KEY (habit_id) REFERENCES habits(habit_id) ON DELETE CASCADE,
                UNIQUE(habit_id, date)
            )
        """)
        print("✅ [DB] Таблица 'habit_logs' создана или уже существует")

        await db.commit()
        print("💾 [DB] Все изменения сохранены")

        # Проверка: какие таблицы есть?
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = await cursor.fetchall()
        print("📋 [DB] Существующие таблицы:", [t[0] for t in tables])

async def add_user(user_id: int, username: str = None):
    """Добавляет пользователя, если его ещё нет"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        await db.commit()
        print(f"👤 [DB] Пользователь {user_id} добавлен или уже существует")

async def add_habit(user_id: int, habit_name: str) -> int | None:
    """Добавляет привычку, если такой ещё нет. Если есть — возвращает существующий ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Сначала проверяем, есть ли уже такая привычка у пользователя
        cursor = await db.execute(
            "SELECT habit_id FROM habits WHERE user_id = ? AND name = ? COLLATE NOCASE",
            (user_id, habit_name)
        )
        existing = await cursor.fetchone()

        if existing:
            habit_id = existing[0]
            print(f"🔁 [DB] Привычка '{habit_name}' уже существует (ID: {habit_id})")
            return habit_id

        # Если не нашли — добавляем новую
        await add_user(user_id)

        cursor = await db.execute(
            "INSERT INTO habits (user_id, name) VALUES (?, ?) RETURNING habit_id",
            (user_id, habit_name)
        )
        row = await cursor.fetchone()
        await db.commit()

        if row:
            habit_id = row[0]
            print(f"📝 [DB] Привычка '{habit_name}' (ID: {habit_id}) добавлена для пользователя {user_id}")
            return habit_id
        else:
            print(f"❌ [DB] Ошибка при добавлении привычки '{habit_name}'")
            return None

async def mark_habit_done(habit_id: int, done: bool = True):
    """Отмечает выполнение привычки на сегодня"""
    today = date.today().isoformat()  # "2025-04-05"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO habit_logs (habit_id, date, done)
            VALUES (?, ?, ?)
            ON CONFLICT(habit_id, date) DO UPDATE SET done = excluded.done
            """,
            (habit_id, today, done)
        )
        await db.commit()
        status = "✅" if done else "❌"
        print(f"[DB] Привычка {habit_id} отмечена как {status} на {today}")

async def get_habit_streak(habit_id: int) -> int:
    """Возвращает текущую цепочку дней подряд (streak)"""
    today = date.today()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT date FROM habit_logs
            WHERE habit_id = ? AND done = 1
            ORDER BY date DESC
            """,
            (habit_id,)
        )
        rows = await cursor.fetchall()

        if not rows:
            return 0

        streak = 0
        expected_date = today

        for (log_date,) in rows:
            log_date = date.fromisoformat(log_date)
            if log_date == expected_date:
                streak += 1
                expected_date = expected_date.replace(day=expected_date.day - 1)
            else:
                break

        return streak

async def get_user_habits(user_id: int):
    """Получает список привычек пользователя: [(habit_id, name), ...]"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT habit_id, name FROM habits WHERE user_id = ?",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return rows

async def get_user_stats(user_id: int):
    """Возвращает статистику пользователя: всего привычек, выполнено/пропущено сегодня, лучшая цепочка"""
    today = date.today().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        # Всего привычек
        cursor = await db.execute("SELECT COUNT(*) FROM habits WHERE user_id = ?", (user_id,))
        total_habits = (await cursor.fetchone())[0]

        # Выполнено сегодня
        cursor = await db.execute("""
            SELECT COUNT(*) FROM habit_logs hl
            JOIN habits h ON hl.habit_id = h.habit_id
            WHERE h.user_id = ? AND hl.date = ? AND hl.done = 1
        """, (user_id, today))
        done_today = (await cursor.fetchone())[0]

        # Пропущено сегодня
        cursor = await db.execute("""
            SELECT COUNT(*) FROM habit_logs hl
            JOIN habits h ON hl.habit_id = h.habit_id
            WHERE h.user_id = ? AND hl.date = ? AND hl.done = 0
        """, (user_id, today))
        skipped_today = (await cursor.fetchone())[0]

        # Лучшая цепочка среди всех привычек
        cursor = await db.execute("""
            SELECT h.name, MAX(streak_table.streak) as max_streak
            FROM habits h
            JOIN (
                SELECT habit_id, COUNT(*) as streak
                FROM (
                    SELECT habit_id, date, done,
                           date(date, '-' || ROW_NUMBER() OVER (PARTITION BY habit_id ORDER BY date DESC) || ' days') as grp
                    FROM habit_logs
                    WHERE done = 1
                )
                GROUP BY habit_id, grp
            ) as streak_table ON h.habit_id = streak_table.habit_id
            WHERE h.user_id = ?
            GROUP BY h.habit_id
            ORDER BY max_streak DESC
            LIMIT 1
        """, (user_id,))
        best_streak_row = await cursor.fetchone()
        best_streak_name = best_streak_row[0] if best_streak_row else None
        best_streak_value = best_streak_row[1] if best_streak_row else 0

        # Текущая цепочка по последней привычке
        cursor = await db.execute("""
            SELECT habit_id, name FROM habits
            WHERE user_id = ?
            ORDER BY habit_id DESC LIMIT 1
        """, (user_id,))
        last_habit = await cursor.fetchone()
        current_streak_name = None
        current_streak_value = 0

        if last_habit:
            habit_id, current_streak_name = last_habit
            current_streak_value = await get_habit_streak(habit_id)

        return {
            "total_habits": total_habits,
            "done_today": done_today,
            "skipped_today": skipped_today,
            "best_streak": {"name": best_streak_name, "value": best_streak_value},
            "current_streak": {"name": current_streak_name, "value": current_streak_value}
        }

async def set_user_reminder_time(user_id: int, reminder_time: str):
    """Устанавливает время напоминания для пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET reminder_time = ? WHERE user_id = ?",
            (reminder_time, user_id)
        )
        await db.commit()
        print(f"⏰ [DB] Установлено время напоминания {reminder_time} для пользователя {user_id}")

async def get_user_reminder_time(user_id: int) -> str | None:
    """Получает время напоминания пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT reminder_time FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] else None

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

async def delete_habit(habit_id: int, user_id: int) -> bool:
    """Удаляет привычку и её логи, если она принадлежит пользователю. Возвращает True, если успешно."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Сначала проверяем, принадлежит ли привычка пользователю
        cursor = await db.execute(
            "SELECT 1 FROM habits WHERE habit_id = ? AND user_id = ?",
            (habit_id, user_id)
        )
        if not await cursor.fetchone():
            return False

        # Удаляем логи
        await db.execute("DELETE FROM habit_logs WHERE habit_id = ?", (habit_id,))
        # Удаляем саму привычку
        await db.execute("DELETE FROM habits WHERE habit_id = ? AND user_id = ?", (habit_id, user_id))
        await db.commit()

        cursor = await db.execute("SELECT changes()")
        changes = await cursor.fetchone()
        return changes[0] > 0
async def reset_user_data(user_id: int) -> bool:
    """Полностью удаляет все привычки и логи пользователя. Возвращает True, если успешно."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Удаляем логи
        await db.execute("DELETE FROM habit_logs WHERE habit_id IN (SELECT habit_id FROM habits WHERE user_id = ?)", (user_id,))
        # Удаляем привычки
        await db.execute("DELETE FROM habits WHERE user_id = ?", (user_id,))
        await db.commit()

        cursor = await db.execute("SELECT changes()")
        changes = await cursor.fetchone()
        return changes[0] > 0  # если 0 — значит, не было данных

async def reset_user_stats_only(user_id: int) -> bool:
    """Удаляет только логи выполнения, привычки остаются"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM habit_logs WHERE habit_id IN (SELECT habit_id FROM habits WHERE user_id = ?)", (user_id,))
        await db.commit()

        cursor = await db.execute("SELECT changes()")
        changes = await cursor.fetchone()
        return changes[0] > 0