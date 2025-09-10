import logging
import os
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram import Router

# === Настройки ===
API_TOKEN = os.getenv("testbot")  # testbot telegram bot token
ADMIN_ID = 167372100  # user_id

logging.basicConfig(level=logging.INFO)

# === Инициализация ===
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# === Клавиатуры ===
def get_start_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Оставить заявку")]
        ],
        resize_keyboard=True
    )

def get_cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

# === База данных ===
def init_db():
    conn = sqlite3.connect("requests.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            device TEXT,
            photo_id TEXT,
            memory TEXT,
            battery TEXT,
            kit TEXT,
            defects TEXT,
            urgency TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def save_request(user_id, username, data):
    conn = sqlite3.connect("requests.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO requests (user_id, username, device, photo_id, memory, battery, kit, defects, urgency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        username,
        data.get("device"),
        data.get("photo_id"),
        data.get("memory"),
        data.get("battery"),
        data.get("kit"),
        data.get("defects"),
        data.get("urgency")
    ))
    conn.commit()
    conn.close()

def get_all_requests():
    conn = sqlite3.connect("requests.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM requests ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return rows

# === Состояния пользователя ===
user_state = {}
questions = [
    ("device", "📱 Модель вашего устройства:"),
    ("photo", "🖼 Отправьте фото устройства:"),
    ("memory", "💾 Введите объем памяти устройства:"),
    ("battery", "🔋 Укажите состояние аккумулятора:"),
    ("kit", "🎁 Опишите комплект (коробка, зарядка и т.д.):"),
    ("defects", "⚠️ Опишите дефекты устройства (если есть):"),
    ("urgency", "⏳ Насколько срочно нужно продать телефон?")
]

# === Хендлеры ===

@router.message(Command("start"))
async def send_welcome(message: Message):
    await message.answer(
        "👋 Привет! Я бот для выкупа устройств.\nНажмите кнопку ниже, чтобы оставить заявку.",
        reply_markup=get_start_kb()
    )

@router.message(F.text == "📱 Оставить заявку")
async def start_request(message: Message):
    user_state[message.from_user.id] = {"step": 0, "data": {}}
    await message.answer(questions[0][1], reply_markup=get_cancel_kb())

@router.message(F.text | F.photo)
async def process_answer(message: Message):
    user_id = message.from_user.id
    if user_id not in user_state:
        return

    step = user_state[user_id]["step"]
    key, _ = questions[step]

    if key == "photo":
        if not message.photo:
            await message.answer("⚠️ Пожалуйста, отправьте фото устройства.")
            return
        user_state[user_id]["data"]["photo_id"] = message.photo[-1].file_id
    else:
        user_state[user_id]["data"][key] = message.text

    step += 1
    if step < len(questions):
        user_state[user_id]["step"] = step
        await message.answer(questions[step][1], reply_markup=get_cancel_kb())
    else:
        data = user_state[user_id]["data"]
        username = message.from_user.username

        save_request(user_id, username, data)

        summary = (
            f"📩 Новая заявка!\n\n"
            f"👤 Пользователь: @{username or user_id}\n"
            f"📱 Модель: {data['device']}\n"
            f"💾 Память: {data['memory']}\n"
            f"🔋 Аккумулятор: {data['battery']}\n"
            f"🎁 Комплект: {data['kit']}\n"
            f"⚠️ Дефекты: {data['defects']}\n"
            f"⏳ Срочность: {data['urgency']}"
        )

        await bot.send_message(ADMIN_ID, summary)
        photo_id = data.get("photo_id")
        if photo_id:
            await bot.send_photo(ADMIN_ID, photo_id)

        await message.answer(
            "✅ Ваша заявка сохранена! Мы скоро свяжемся с вами.",
            reply_markup=get_start_kb()
        )
        user_state.pop(user_id, None)

@router.message(Command("list"))
async def list_requests(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав для этой команды.")
        return

    rows = get_all_requests()
    if not rows:
        await message.answer("📭 Пока нет заявок.")
        return

    for req in rows[:10]:
        req_id, user_id, username, device, photo_id, memory, battery, kit, defects, urgency = req
        caption = (
            f"📌 Заявка #{req_id}\n\n"
            f"👤 Пользователь: @{username or user_id}\n"
            f"📱 Модель: {device}\n"
            f"💾 Память: {memory}\n"
            f"🔋 Аккумулятор: {battery}\n"
            f"🎁 Комплект: {kit}\n"
            f"⚠️ Дефекты: {defects}\n"
            f"⏳ Срочность: {urgency}"
        )
        if photo_id:
            await bot.send_photo(message.chat.id, photo_id, caption=caption)
        else:
            await message.answer(caption)

# === Запуск ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

