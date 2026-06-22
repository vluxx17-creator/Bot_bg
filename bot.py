import asyncio
import csv
import io
import json
import os
import re
import tempfile
from pathlib import Path
from aiohttp import web

import aiohttp
import gdown
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
FILE_MAP_URL = os.getenv("FILE_MAP_URL", "https://gist.githubusercontent.com/vluxx17-creator/743a7f3bf86fc2e35a88bdbee2c6771f/raw/2edbca8d5da11e3fe46a173dd097117985edf4d3/gistfile1.txt")
INDEX_URL = os.getenv("INDEX_URL", "")

GDOWN_TEMPLATE = "https://drive.google.com/uc?id={file_id}"

file_map = {}
phone_index = {}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class SearchStates(StatesGroup):
    waiting_for_phone = State()

main_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📱 Поиск по номеру телефона", callback_data="search_phone")]
])
cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
])

def clean_phone(raw: str) -> str:
    digits = re.sub(r'\D', '', raw)
    if len(digits) == 11 and digits[0] in ('7', '8'):
        return digits[1:]
    return digits

async def download_json(url: str) -> dict | None:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                try:
                    return await resp.json()
                except Exception:
                    return None
    return None

async def load_mappings():
    global file_map, phone_index
    print(f"FILE_MAP_URL = {FILE_MAP_URL}")
    if FILE_MAP_URL:
        fm = await download_json(FILE_MAP_URL)
        print(f"download_json result: {fm}")
        if fm:
            file_map = fm
    if INDEX_URL:
        idx = await download_json(INDEX_URL)
        if idx:
            phone_index = idx
    print(f"Загружено {len(file_map)} файлов, {len(phone_index)} префиксов")

def download_file_from_drive(file_id: str) -> Path:
    url = GDOWN_TEMPLATE.format(file_id=file_id)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp_path = Path(tmp.name)
    gdown.download(url, str(tmp_path), quiet=True)
    if tmp_path.stat().st_size == 0:
        tmp_path.unlink(missing_ok=True)
        return None
    return tmp_path

def search_in_file(file_path: Path, phone_clean: str) -> dict | None:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if phone_clean in line:
                delimiter = "\t" if "\t" in line else ","
                reader = csv.reader(io.StringIO(line), quotechar='"', delimiter=delimiter)
                for row in reader:
                    for cell in row:
                        if clean_phone(cell) == phone_clean:
                            return parse_row(row)
    return None

def parse_row(row: list) -> dict:
    if len(row) >= 5:
        return {
            "id": row[0] if row[0] != "NULL" else "",
            "username": row[1] if row[1] != "NULL" else "",
            "first_name": row[2].strip('"') if row[2] != "NULL" else "",
            "last_name": row[3].strip('"') if len(row) > 3 and row[3] != "NULL" else "",
            "phone": row[4] if len(row) > 4 else ""
        }
    else:
        return {"raw": " | ".join(row)}

async def search_by_phone(phone: str) -> str:
    clean = clean_phone(phone)
    if len(clean) < 10:
        return "❌ Некорректный номер"
    prefix = clean[:3]
    if prefix not in phone_index:
        return "❌ Номер не найден в индексе"
    file_names = phone_index[prefix]
    for fname in file_names:
        file_id = file_map.get(fname)
        if not file_id:
            continue
        file_path = download_file_from_drive(file_id)
        if not file_path:
            continue
        result = search_in_file(file_path, clean)
        file_path.unlink(missing_ok=True)
        if result:
            lines = [f"📱 Номер: {phone}"]
            name = f"{result.get('first_name','')} {result.get('last_name','')}".strip()
            if name:
                lines.append(f"👤 Имя: {name}")
            if result.get("username"):
                lines.append(f"🆔 Telegram: @{result['username']}")
            if result.get("id"):
                lines.append(f"🔢 ID: {result['id']}")
            if result.get("raw"):
                lines.append(f"📋 Данные: {result['raw']}")
            lines.append("🟢 Найдено в базе")
            return "\n".join(lines)
    return "❌ Номер не найден"

@dp.message(Command("build_index"))
async def cmd_build_index(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Доступ запрещён")
    if not file_map:
        return await message.answer("❌ Не загружен file_map.json. Проверьте FILE_MAP_URL.")
    await message.answer("⏳ Начинаю построение индекса. Это может занять несколько минут...")
    new_index = {}
    processed = 0
    errors = []
    for fname, file_id in file_map.items():
        file_path = download_file_from_drive(file_id)
        if not file_path:
            errors.append(f"{fname}: не удалось скачать")
            continue
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.strip():
                        digits = re.findall(r'\d+', line)
                        for d in digits:
                            cleaned = clean_phone(d)
                            if len(cleaned) >= 10:
                                prefix = cleaned[:3]
                                if prefix not in new_index:
                                    new_index[prefix] = []
                                if fname not in new_index[prefix]:
                                    new_index[prefix].append(fname)
            processed += 1
        except Exception as e:
            errors.append(f"{fname}: {e}")
        finally:
            file_path.unlink(missing_ok=True)
    index_json = json.dumps(new_index, ensure_ascii=False, indent=2)
    bio = BytesIO(index_json.encode('utf-8'))
    bio.name = "index.json"
    caption = f"✅ Индекс построен. Обработано файлов: {processed}"
    if errors:
        caption += f"\nОшибок: {len(errors)}"
    await message.answer_document(FSInputFile(bio), caption=caption)
    await message.answer("⚠️ Загрузи этот index.json на GitHub Gist (как и file_map.json), получи raw-ссылку и укажи её в переменной INDEX_URL на Render, затем перезапусти бота.")

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("🔍 Поиск по номеру телефона в большой базе данных.\nВыберите действие:", reply_markup=main_kb)

@dp.callback_query(F.data == "search_phone")
async def ask_phone(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SearchStates.waiting_for_phone)
    await callback.message.answer("Введите номер телефона (с кодом страны или без):", reply_markup=cancel_kb)
    await callback.answer()

@dp.callback_query(F.data == "cancel")
async def cancel_search(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Поиск отменён.", reply_markup=main_kb)
    await callback.answer()

@dp.message(SearchStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    await state.clear()
    await message.answer("⏳ Ищу...")
    result = await search_by_phone(phone)
    await message.answer(result, reply_markup=main_kb)

async def health_check(request):
    return web.Response(text="OK")

async def run_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Health-сервер запущен на порту {port}")

async def main():
    await load_mappings()
    await asyncio.gather(
        run_web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
