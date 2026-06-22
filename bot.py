import asyncio
import csv
import io
import json
import os
import re
import tempfile
from pathlib import Path
from aiohttp import web
from concurrent.futures import ThreadPoolExecutor

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
INDEX_URL = os.getenv("INDEX_URL", "")

GDOWN_TEMPLATE = "https://drive.google.com/uc?id={file_id}"

FILE_MAP = {
    "school_1.csv": "1N-sJV5GR5I-thsH9mjOAgPhyO8VYk29k",
    "school_3.csv": "1342Gl23P314oisuCn1hyAT2kXzpJ4L_i",
    "school_6.csv": "16bAziCf56Ykaw1njC2oVTXSFCoIhLyi_",
    "gosuslugi_1.csv": "1oqDrFeQLo6cou96I7S9h4FQ8ILUW4yd3",
    "moscow_1.txt": "1rkoXdEiX47BVuDJTqGyEfaLEgl5W5Q49",
    "Telegram_1.csv": "1gPxZxtv0WzJQB2wbPrSW9dp7cAzRQLMw",
    "Telegram_2.txt": "1CbYkhEMyChN_61qpa_szxumB6JtBBqGn",
    "Telegram_3.txt": "1rgq5ABpH2p3PoIBLYh5T980rYCrPYJMB",
    "Telegram_4.txt": "1Li4LjlbwxK5dOAUyp87U9AQe_CtDpnqv"
}

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

# Пул потоков для фоновых задач
executor = ThreadPoolExecutor(max_workers=2)

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

async def load_index():
    global phone_index
    if INDEX_URL:
        idx = await download_json(INDEX_URL)
        if idx:
            phone_index = idx
            print(f"Индекс загружен, {len(phone_index)} префиксов")
        else:
            print("Не удалось загрузить индекс")
    else:
        print("INDEX_URL не задан, индекс не загружен")

def _download_file_sync(file_id: str) -> Path | None:
    """Синхронная загрузка файла с Google Диска (выполняется в потоке)"""
    url = GDOWN_TEMPLATE.format(file_id=file_id)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp_path = Path(tmp.name)
    try:
        gdown.download(url, str(tmp_path), quiet=True)
        if tmp_path.stat().st_size == 0:
            tmp_path.unlink(missing_ok=True)
            return None
        return tmp_path
    except Exception:
        tmp_path.unlink(missing_ok=True)
        return None

async def download_file_from_drive(file_id: str) -> Path | None:
    """Асинхронная обёртка над _download_file_sync с таймаутом"""
    try:
        return await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(executor, _download_file_sync, file_id),
            timeout=300  # 5 минут на файл
        )
    except asyncio.TimeoutError:
        print(f"Таймаут загрузки файла {file_id}")
        return None

def _search_in_file_sync(file_path: Path, phone_clean: str) -> dict | None:
    """Синхронный поиск в файле (выполняется в потоке)"""
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

async def search_in_file(file_path: Path, phone_clean: str) -> dict | None:
    """Асинхронная обёртка поиска в файле"""
    return await asyncio.get_event_loop().run_in_executor(executor, _search_in_file_sync, file_path, phone_clean)

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
        file_id = FILE_MAP.get(fname)
        if not file_id:
            continue
        file_path = await download_file_from_drive(file_id)
        if not file_path:
            continue
        result = await search_in_file(file_path, clean)
        # Удаляем файл в фоне
        asyncio.create_task(delete_file_async(file_path))
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

async def delete_file_async(file_path: Path):
    """Удаление файла в потоке, чтобы не блокировать event loop"""
    await asyncio.get_event_loop().run_in_executor(executor, file_path.unlink, True)

@dp.message(Command("build_index"))
async def cmd_build_index(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Доступ запрещён")
    await message.answer("⏳ Начинаю построение индекса. Это займёт время (возможно, 10-20 минут). Пожалуйста, не прерывайте.")
    new_index = {}
    processed = 0
    errors = []
    # Чтобы health-check не убил процесс, запускаем индексацию в фоне и периодически обновляем статус
    for fname, file_id in FILE_MAP.items():
        file_path = await download_file_from_drive(file_id)
        if not file_path:
            errors.append(f"{fname}: не удалось скачать")
            continue
        try:
            # Читаем файл асинхронно (в потоке)
            def _process_file(fp):
                """Функция, выполняемая в потоке для индексации файла"""
                local_index = {}
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.strip():
                            digits = re.findall(r'\d+', line)
                            for d in digits:
                                cleaned = clean_phone(d)
                                if len(cleaned) >= 10:
                                    prefix = cleaned[:3]
                                    if prefix not in local_index:
                                        local_index[prefix] = set()
                                    local_index[prefix].add(fname)
                return local_index
            local_index = await asyncio.get_event_loop().run_in_executor(executor, _process_file, file_path)
            # Объединяем в общий индекс
            for prefix, names in local_index.items():
                if prefix not in new_index:
                    new_index[prefix] = []
                for name in names:
                    if name not in new_index[prefix]:
                        new_index[prefix].append(name)
            processed += 1
        except Exception as e:
            errors.append(f"{fname}: {e}")
        finally:
            await delete_file_async(file_path)
        # Даем event loop обработать другие задачи (например, health-check)
        await asyncio.sleep(0.1)

    if not new_index and errors:
        await message.answer(f"❌ Не удалось построить индекс. Ошибки: {', '.join(errors[:5])}")
        return

    index_json = json.dumps(new_index, ensure_ascii=False, indent=2)
    bio = BytesIO(index_json.encode('utf-8'))
    bio.name = "index.json"
    caption = f"✅ Индекс построен. Обработано файлов: {processed}"
    if errors:
        caption += f"\nОшибок: {len(errors)}"
    await message.answer_document(FSInputFile(bio), caption=caption)
    await message.answer("⚠️ Отправь этот файл мне, я зашью его в код бота.")

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

# Health-check веб-сервер
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
    await load_index()
    await asyncio.gather(
        run_web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
