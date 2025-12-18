import asyncio
import os
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

TOKEN = "8238770622:AAHDD5S5DffLH7fDY8BGg05RA7OB6kKWdo4"
ADMINS = [2003036238, 6403436200]

bot = Bot(os.getenv("TOKEN"))
dp = Dispatcher()

WELCOME_TEXT = """
💙 <b>Привет. Ты не один.</b>
( Наш тгк - https://t.me/Glebarz )

Я — бот поддержки.
Я здесь, чтобы помочь тебе в трудный момент, выслушать и направить к человеку, который сможет поддержать.

📌 <b>Как это работает:</b>
• Напиши /start — выбери администратора  
• После выбора можешь писать всё, что тебя волнует  
• Если хочешь другого администратора — снова /start  

🤍 Пиши свободно. Здесь стараются понять и помочь.

<b>Запрещено:</b>
1️⃣ 18+ контент  
2️⃣ спам  
3️⃣ оскорбления  
4️⃣ сторонние ссылки  
5️⃣ выпрашивание личных данных  
6️⃣ менять администратора больше 3 раз  

⏱ Если админ не ответил 10 минут — продублируй сообщение
"""


# ====== БД ======
db = sqlite3.connect("bot.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    admin_id INTEGER,
    alias TEXT,
    active_user INTEGER
)
""")
db.commit()

# инициализация админов
for aid in ADMINS:
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (aid,))
db.commit()

# ====== HELPERS ======

def set_user(uid, username):
    cur.execute("""
        INSERT INTO users (user_id, username)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET username=excluded.username
    """, (uid, username))
    db.commit()

def ensure_column(table, column, definition):
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        db.commit()

ensure_column("users", "active_user", "INTEGER")

def set_alias(uid, alias):
    cur.execute("UPDATE users SET alias=? WHERE user_id=?", (alias, uid))
    db.commit()

def get_admins_with_alias():
    cur.execute("SELECT user_id, alias FROM users WHERE alias IS NOT NULL")
    return cur.fetchall()

def bind_user(user_id, admin_id):
    cur.execute("UPDATE users SET admin_id=? WHERE user_id=?", (admin_id, user_id))
    db.commit()

def get_admin(user_id):
    cur.execute("SELECT admin_id FROM users WHERE user_id=?", (user_id,))
    r = cur.fetchone()
    return r[0] if r else None

def set_active_user(admin_id, user_id):
    cur.execute("UPDATE users SET active_user=? WHERE user_id=?", (user_id, admin_id))
    db.commit()

def get_active_user(admin_id):
    cur.execute("SELECT active_user FROM users WHERE user_id=?", (admin_id,))
    r = cur.fetchone()
    return r[0] if r else None

def get_admin_users(admin_id):
    cur.execute("SELECT user_id, username FROM users WHERE admin_id=?", (admin_id,))
    return cur.fetchall()

# ====== KEYBOARDS ======

def admins_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"#{alias}", callback_data=f"admin_{aid}")]
            for aid, alias in get_admins_with_alias()
        ]
    )

def users_kb(admin_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"@{username or uid}",
                callback_data=f"user_{uid}"
            )]
            for uid, username in get_admin_users(admin_id)
        ]
    )

# ====== START ======

@dp.message(F.text == "/start")
async def start(message: Message):
    uid = message.from_user.id
    set_user(uid, message.from_user.username)

    if uid in ADMINS:
        cur.execute("SELECT alias FROM users WHERE user_id=?", (uid,))
        alias = cur.fetchone()[0]

        if not alias:
            await message.answer("Вы администратор. Установите псевдоним:\n#Глеб")
        else:
            await message.answer(
                f"Администратор {alias}\nВыберите пользователя:",
                reply_markup=users_kb(uid)
            )
        return

    # --- ПОЛЬЗОВАТЕЛЬ ---
    kb = admins_kb()
    if not kb.inline_keyboard:
           await message.answer("Нет доступных администраторов.")
           return

    await message.answer(WELCOME_TEXT)
    await message.answer(
    "Выберите администратора:",
    reply_markup=kb
)


# ====== SET ALIAS ======

@dp.message(F.from_user.id.in_(ADMINS), F.text.startswith("#"))
async def alias(message: Message):
    name = message.text[1:].strip()
    if not name or " " in name:
        await message.answer("Некорректный псевдоним.")
        return

    set_alias(message.from_user.id, name)
    await message.answer(f"Псевдоним установлен: #{name}")

# ====== PICK ADMIN ======

@dp.callback_query(F.data.startswith("admin_"))
async def pick_admin(cb: CallbackQuery):
    admin_id = int(cb.data.split("_")[1])
    bind_user(cb.from_user.id, admin_id)

    await cb.message.answer("Можете писать сообщение.")
    await bot.send_message(admin_id, "Новый пользователь.")
    await cb.answer()

# ====== PICK USER (ADMIN) ======

@dp.callback_query(F.data.startswith("user_"))
async def pick_user(cb: CallbackQuery):
    uid = int(cb.data.split("_")[1])
    set_active_user(cb.from_user.id, uid)
    await cb.message.answer("Пользователь выбран.")
    await cb.answer()

# ====== USER -> ADMIN ======

@dp.message(F.from_user.id.not_in(ADMINS))
async def user_to_admin(message: Message):
    admin_id = get_admin(message.from_user.id)
    if not admin_id:
        return

    username = message.from_user.username
    label = f"От: @{username}" if username else f"От: ID {message.from_user.id}"

    # подпись
    await bot.send_message(admin_id, label)

    # копия сообщения (любой тип)
    await bot.copy_message(
        chat_id=admin_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )





# ====== ADMIN -> USER ======

@dp.message(F.from_user.id.in_(ADMINS))
async def admin_to_user(message: Message):
    user_id = get_active_user(message.from_user.id)
    if not user_id:
        await message.answer("Выберите пользователя.")
        return

    cur.execute("SELECT alias FROM users WHERE user_id=?", (message.from_user.id,))
    row = cur.fetchone()
    alias = row[0] if row and row[0] else "Администратор"

    # подпись
    await bot.send_message(user_id, f"От: #{alias}")

    # копия сообщения
    await bot.copy_message(
        chat_id=user_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )


# ====== RUN ======

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
