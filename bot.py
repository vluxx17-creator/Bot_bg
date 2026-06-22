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

GDOWN_TEMPLATE = "https://drive.google.com/uc?id={file_id}"

# Вшитый file_map (без загрузок)
FILE_MAP = {
    "Telegram_1.csv": "1gPxZxtv0WzJQB2wbPrSW9dp7cAzRQLMw",
    "Telegram_2.txt": "1CbYkhEMyChN_61qpa_szxumB6JtBBqGn",
    "Telegram_3.txt": "1rgq5ABpH2p3PoIBLYh5T980rYCrPYJMB",
    "Telegram_4.txt": "1Li4LjlbwxK5dOAUyp87U9AQe_CtDpnqv",
    "school_1.csv": "1N-sJV5GR5I-thsH9mjOAgPhyO8VYk29k",
    "school_3.csv": "1342Gl23P314oisuCn1hyAT2kXzpJ4L_i",
    "school_6.csv": "16bAziCf56Ykaw1njC2oVTXSFCoIhLyi_",
    "gosuslugi_1.csv": "1oqDrFeQLo6cou96I7S9h4FQ8ILUW4yd3",
    "moscow_1.txt": "1rkoXdEiX47BVuDJTqGyEfaLEgl5W5Q49"
}

# Вшитый индекс
PHONE_INDEX = {
  "380": ["Telegram_1.csv"],
  "925": ["Telegram_1.csv"],
  "375": ["Telegram_1.csv"],
  "987": ["Telegram_1.csv"],
  "905": ["Telegram_1.csv"],
  "926": ["Telegram_1.csv"],
  "927": ["Telegram_1.csv"],
  "960": ["Telegram_1.csv"],
  "998": ["Telegram_1.csv"],
  "912": ["Telegram_1.csv"],
  "914": ["Telegram_1.csv"],
  "977": ["Telegram_1.csv","Telegram_2.txt"],
  "906": ["Telegram_1.csv"],
  "921": ["Telegram_1.csv"],
  "916": ["Telegram_1.csv","Telegram_4.txt"],
  "902": ["Telegram_1.csv"],
  "917": ["Telegram_1.csv","Telegram_4.txt"],
  "922": ["Telegram_1.csv"],
  "967": ["Telegram_1.csv"],
  "903": ["Telegram_1.csv"],
  "909": ["Telegram_1.csv"],
  "995": ["Telegram_1.csv"],
  "915": ["Telegram_1.csv"],
  "983": ["Telegram_1.csv"],
  "913": ["Telegram_1.csv"],
  "919": ["Telegram_1.csv"],
  "923": ["Telegram_1.csv"],
  "901": ["Telegram_1.csv"],
  "989": ["Telegram_1.csv"],
  "962": ["Telegram_1.csv"],
  "929": ["Telegram_1.csv"],
  "963": ["Telegram_1.csv"],
  "961": ["Telegram_1.csv"],
  "928": ["Telegram_1.csv"],
  "911": ["Telegram_1.csv"],
  "982": ["Telegram_1.csv"],
  "161": ["Telegram_1.csv","Telegram_2.txt"],
  "700": ["Telegram_1.csv","Telegram_2.txt"],
  "968": ["Telegram_1.csv"],
  "701": ["Telegram_1.csv","Telegram_2.txt"],
  "937": ["Telegram_1.csv"],
  "420": ["Telegram_1.csv"],
  "964": ["Telegram_1.csv"],
  "920": ["Telegram_1.csv"],
  "985": ["Telegram_1.csv"],
  "910": ["Telegram_1.csv"],
  "981": ["Telegram_1.csv"],
  "999": ["Telegram_1.csv"],
  "707": ["Telegram_1.csv","Telegram_2.txt"],
  "971": ["Telegram_1.csv"],
  "702": ["Telegram_1.csv","Telegram_2.txt"],
  "965": ["Telegram_1.csv"],
  "931": ["Telegram_1.csv"],
  "966": ["Telegram_1.csv"],
  "988": ["Telegram_1.csv"],
  "951": ["Telegram_1.csv"],
  "986": ["Telegram_1.csv"],
  "952": ["Telegram_1.csv"],
  "777": ["Telegram_1.csv","Telegram_2.txt"],
  "918": ["Telegram_1.csv"],
  "778": ["Telegram_1.csv","Telegram_2.txt"],
  "163": ["Telegram_1.csv","Telegram_2.txt"],
  "932": ["Telegram_1.csv"],
  "191": ["Telegram_1.csv"],
  "980": ["Telegram_1.csv"],
  "972": ["Telegram_1.csv"],
  "346": ["Telegram_1.csv"],
  "371": ["Telegram_1.csv"],
  "601": ["Telegram_1.csv"],
  "996": ["Telegram_1.csv"],
  "953": ["Telegram_1.csv"],
  "908": ["Telegram_1.csv"],
  "316": ["Telegram_1.csv"],
  "705": ["Telegram_1.csv","Telegram_2.txt"],
  "969": ["Telegram_1.csv"],
  "393": ["Telegram_1.csv"],
  "904": ["Telegram_1.csv","Telegram_4.txt"],
  "775": ["Telegram_1.csv","Telegram_2.txt"],
  "141": ["Telegram_1.csv","Telegram_2.txt"],
  "994": ["Telegram_1.csv"],
  "950": ["Telegram_1.csv","Telegram_4.txt"],
  "487": ["Telegram_1.csv"],
  "373": ["Telegram_1.csv"],
  "747": ["Telegram_1.csv","Telegram_2.txt"],
  "417": ["Telegram_1.csv"],
  "933": ["Telegram_1.csv"],
  "447": ["Telegram_1.csv"],
  "491": ["Telegram_1.csv"],
  "357": ["Telegram_1.csv"],
  "134": ["Telegram_1.csv"],
  "900": ["Telegram_1.csv"],
  "177": ["Telegram_1.csv","Telegram_2.txt"],
  "708": ["Telegram_1.csv","Telegram_2.txt"],
  "789": ["Telegram_1.csv"],
  "347": ["Telegram_1.csv"],
  "000": ["Telegram_1.csv"],
  "374": ["Telegram_1.csv"],
  "485": ["Telegram_1.csv"],
  "974": ["Telegram_1.csv"],
  "372": ["Telegram_1.csv"],
  "978": ["Telegram_1.csv"],
  "938": ["Telegram_1.csv"],
  "370": ["Telegram_1.csv"],
  "924": ["Telegram_1.csv"],
  "958": ["Telegram_1.csv"],
  "324": ["Telegram_1.csv"],
  "121": ["Telegram_1.csv","Telegram_2.txt"],
  "352": ["Telegram_1.csv"],
  "174": ["Telegram_1.csv","Telegram_2.txt"],
  "930": ["Telegram_1.csv"],
  "771": ["Telegram_1.csv","Telegram_2.txt"],
  "639": ["Telegram_1.csv"],
  "992": ["Telegram_1.csv"],
  "436": ["Telegram_1.csv"],
  "336": ["Telegram_1.csv"],
  "939": ["Telegram_1.csv"],
  "152": ["Telegram_1.csv","Telegram_2.txt"],
  "171": ["Telegram_1.csv","Telegram_2.txt"],
  "165": ["Telegram_1.csv","Telegram_2.txt"],
  "386": ["Telegram_1.csv"],
  "140": ["Telegram_1.csv","Telegram_2.txt"],
  "666": ["Telegram_1.csv"],
  "367": ["Telegram_1.csv"],
  "984": ["Telegram_1.csv"],
  "358": ["Telegram_1.csv"],
  "194": ["Telegram_1.csv"],
  "991": ["Telegram_1.csv"],
  "359": ["Telegram_1.csv"],
  "164": ["Telegram_1.csv","Telegram_2.txt"],
  "178": ["Telegram_1.csv"],
  "668": ["Telegram_1.csv"],
  "126": ["Telegram_1.csv","Telegram_2.txt"],
  "351": ["Telegram_1.csv"],
  "614": ["Telegram_1.csv"],
  "142": ["Telegram_1.csv","Telegram_2.txt"],
  "407": ["Telegram_1.csv"],
  "381": ["Telegram_1.csv"],
  "467": ["Telegram_1.csv"],
  "936": ["Telegram_1.csv"],
  "067": ["Telegram_1.csv"],
  "356": ["Telegram_1.csv"],
  "172": ["Telegram_1.csv"],
  "001": ["Telegram_1.csv"],
  "488": ["Telegram_1.csv"],
  "184": ["Telegram_1.csv"],
  "776": ["Telegram_1.csv","Telegram_2.txt"],
  "940": ["Telegram_1.csv"],
  "158": ["Telegram_1.csv"],
  "130": ["Telegram_1.csv","Telegram_2.txt"],
  "151": ["Telegram_1.csv","Telegram_2.txt"],
  "382": ["Telegram_1.csv"],
  "993": ["Telegram_1.csv"],
  "131": ["Telegram_1.csv"],
  "481": ["Telegram_1.csv"],
  "337": ["Telegram_1.csv"],
  "353": ["Telegram_1.csv"],
  "192": ["Telegram_1.csv"],
  "706": ["Telegram_1.csv","Telegram_2.txt"],
  "278": ["Telegram_1.csv"],
  "097": ["Telegram_1.csv"],
  "190": ["Telegram_1.csv"],
  "486": ["Telegram_1.csv"],
  "050": ["Telegram_1.csv"],
  "223": ["Telegram_1.csv"],
  "156": ["Telegram_1.csv","Telegram_2.txt"],
  "066": ["Telegram_1.csv"],
  "934": ["Telegram_1.csv"],
  "093": ["Telegram_1.csv"],
  "185": ["Telegram_1.csv","Telegram_2.txt"],
  "181": ["Telegram_1.csv","Telegram_2.txt"],
  "195": ["Telegram_1.csv"],
  "068": ["Telegram_1.csv"],
  "408": ["Telegram_1.csv"],
  "199": ["Telegram_1.csv"],
  "096": ["Telegram_1.csv"],
  "091": ["Telegram_1.csv"],
  "122": ["Telegram_1.csv","Telegram_2.txt"],
  "306": ["Telegram_1.csv"],
  "111": ["Telegram_1.csv","Telegram_2.txt"],
  "010": ["Telegram_1.csv"],
  "363": ["Telegram_1.csv"],
  "421": ["Telegram_1.csv"],
  "186": ["Telegram_1.csv"],
  "123": ["Telegram_1.csv","Telegram_2.txt"],
  "162": ["Telegram_1.csv","Telegram_2.txt"],
  "888": ["Telegram_1.csv"],
  "573": ["Telegram_1.csv"],
  "170": ["Telegram_1.csv","Telegram_2.txt"],
  "063": ["Telegram_1.csv"],
  "150": ["Telegram_1.csv"],
  "193": ["Telegram_1.csv"],
  "173": ["Telegram_1.csv","Telegram_2.txt"],
  "133": ["Telegram_1.csv","Telegram_2.txt"],
  "120": ["Telegram_1.csv","Telegram_2.txt"],
  "642": ["Telegram_1.csv"],
  "362": ["Telegram_1.csv"],
  "378": ["Telegram_1.csv"],
  "201": ["Telegram_1.csv"],
  "148": ["Telegram_1.csv","Telegram_2.txt"],
  "125": ["Telegram_1.csv","Telegram_2.txt"],
  "249": ["Telegram_1.csv"],
  "157": ["Telegram_1.csv","Telegram_2.txt"],
  "204": ["Telegram_1.csv"],
  "144": ["Telegram_1.csv","Telegram_2.txt"],
  "099": ["Telegram_1.csv"],
  "112": ["Telegram_1.csv","Telegram_2.txt"],
  "609": ["Telegram_1.csv"],
  "012": ["Telegram_1.csv"],
  "577": ["Telegram_1.csv"],
  "800": ["Telegram_1.csv"],
  "180": ["Telegram_1.csv"],
  "098": ["Telegram_1.csv"],
  "526": ["Telegram_1.csv"],
  "628": ["Telegram_1.csv"],
  "555": ["Telegram_1.csv"],
  "799": ["Telegram_1.csv"],
  "197": ["Telegram_1.csv"],
  "234": ["Telegram_1.csv"],
  "155": ["Telegram_1.csv"],
  "136": ["Telegram_1.csv","Telegram_2.txt"],
  "389": ["Telegram_1.csv"],
  "160": ["Telegram_1.csv","Telegram_2.txt"],
  "095": ["Telegram_1.csv"],
  "849": ["Telegram_1.csv"],
  "039": ["Telegram_1.csv"],
  "228": ["Telegram_1.csv"],
  "212": ["Telegram_1.csv"],
  "333": ["Telegram_1.csv"],
  "114": ["Telegram_1.csv","Telegram_2.txt"],
  "787": ["Telegram_1.csv"],
  "528": ["Telegram_1.csv"],
  "584": ["Telegram_1.csv"],
  "105": ["Telegram_1.csv","Telegram_2.txt"],
  "522": ["Telegram_1.csv"],
  "020": ["Telegram_1.csv"],
  "531": ["Telegram_1.csv"],
  "182": ["Telegram_1.csv"],
  "176": ["Telegram_1.csv","Telegram_2.txt"],
  "060": ["Telegram_1.csv"],
  "102": ["Telegram_1.csv","Telegram_2.txt"],
  "143": ["Telegram_1.csv","Telegram_2.txt"],
  "569": ["Telegram_1.csv"],
  "132": ["Telegram_1.csv","Telegram_2.txt"],
  "138": ["Telegram_1.csv","Telegram_2.txt"],
  "970": ["Telegram_1.csv"],
  "166": ["Telegram_1.csv","Telegram_2.txt"],
  "557": ["Telegram_1.csv"],
  "071": ["Telegram_1.csv"],
  "187": ["Telegram_1.csv","Telegram_2.txt"],
  "167": ["Telegram_1.csv","Telegram_2.txt"],
  "183": ["Telegram_1.csv"],
  "891": ["Telegram_1.csv"],
  "202": ["Telegram_1.csv"],
  "676": ["Telegram_1.csv"],
  "175": ["Telegram_1.csv"],
  "828": ["Telegram_1.csv"],
  "348": ["Telegram_1.csv"],
  "470": ["Telegram_1.csv"],
  "947": ["Telegram_1.csv"],
  "198": ["Telegram_1.csv"],
  "282": ["Telegram_1.csv"],
  "203": ["Telegram_1.csv"],
  "727": ["Telegram_1.csv"],
  "229": ["Telegram_1.csv"],
  "222": ["Telegram_1.csv"],
  "552": ["Telegram_1.csv"],
  "554": ["Telegram_1.csv"],
  "444": ["Telegram_1.csv"],
  "101": ["Telegram_1.csv","Telegram_2.txt"],
  "216": ["Telegram_1.csv"],
  "215": ["Telegram_1.csv"],
  "521": ["Telegram_1.csv"],
  "154": ["Telegram_1.csv","Telegram_2.txt"],
  "519": ["Telegram_1.csv"],
  "385": ["Telegram_1.csv"],
  "244": ["Telegram_1.csv"],
  "124": ["Telegram_1.csv","Telegram_2.txt"],
  "542": ["Telegram_1.csv"],
  "277": ["Telegram_1.csv"],
  "627": ["Telegram_1.csv"],
  "100": ["Telegram_1.csv","Telegram_2.txt"],
  "443": ["Telegram_1.csv"],
  "798": ["Telegram_1.csv"],
  "250": ["Telegram_1.csv"],
  "255": ["Telegram_1.csv"],
  "103": ["Telegram_1.csv","Telegram_2.txt"],
  "104": ["Telegram_1.csv","Telegram_2.txt"],
  "369": ["Telegram_1.csv"],
  "736": ["Telegram_1.csv"],
  "264": ["Telegram_1.csv"],
  "106": ["Telegram_1.csv","Telegram_2.txt"],
  "558": ["Telegram_1.csv"],
  "263": ["Telegram_1.csv"],
  "107": ["Telegram_1.csv","Telegram_2.txt"],
  "256": ["Telegram_1.csv"],
  "284": ["Telegram_1.csv"],
  "551": ["Telegram_1.csv"],
  "108": ["Telegram_1.csv","Telegram_2.txt"],
  "507": ["Telegram_1.csv"],
  "109": ["Telegram_1.csv","Telegram_2.txt"],
  "271": ["Telegram_1.csv"],
  "110": ["Telegram_1.csv","Telegram_2.txt"],
  "147": ["Telegram_1.csv","Telegram_2.txt"],
  "135": ["Telegram_1.csv","Telegram_2.txt"],
  "113": ["Telegram_1.csv","Telegram_2.txt"],
  "976": ["Telegram_1.csv"],
  "826": ["Telegram_1.csv"],
  "055": ["Telegram_1.csv"],
  "115": ["Telegram_1.csv","Telegram_2.txt"],
  "790": ["Telegram_1.csv"],
  "116": ["Telegram_1.csv","Telegram_2.txt"],
  "117": ["Telegram_1.csv","Telegram_2.txt"],
  "118": ["Telegram_1.csv","Telegram_2.txt"],
  "251": ["Telegram_1.csv"],
  "119": ["Telegram_1.csv","Telegram_2.txt"],
  "230": ["Telegram_1.csv"],
  "559": ["Telegram_1.csv"],
  "231": ["Telegram_1.csv"],
  "656": ["Telegram_1.csv"],
  "146": ["Telegram_1.csv","Telegram_2.txt"],
  "253": ["Telegram_1.csv"],
  "541": ["Telegram_1.csv"],
  "094": ["Telegram_1.csv"],
  "127": ["Telegram_1.csv","Telegram_2.txt"],
  "128": ["Telegram_1.csv","Telegram_2.txt"],
  "209": ["Telegram_1.csv"],
  "129": ["Telegram_1.csv","Telegram_2.txt"],
  "797": ["Telegram_1.csv"],
  "312": ["Telegram_1.csv"],
  "041": ["Telegram_1.csv"],
  "073": ["Telegram_1.csv"],
  "200": ["Telegram_1.csv"],
  "224": ["Telegram_1.csv"],
  "504": ["Telegram_1.csv"],
  "830": ["Telegram_1.csv"],
  "618": ["Telegram_1.csv"],
  "221": ["Telegram_1.csv"],
  "525": ["Telegram_1.csv"],
  "892": ["Telegram_1.csv"],
  "137": ["Telegram_1.csv","Telegram_2.txt"],
  "139": ["Telegram_1.csv","Telegram_2.txt"],
  "593": ["Telegram_1.csv"],
  "293": ["Telegram_1.csv"],
  "774": ["Telegram_1.csv"],
  "499": ["Telegram_1.csv"],
  "973": ["Telegram_1.csv"],
  "959": ["Telegram_1.csv"],
  "179": ["Telegram_1.csv","Telegram_2.txt"],
  "405": ["Telegram_1.csv"],
  "844": ["Telegram_1.csv"],
  "299": ["Telegram_1.csv"],
  "233": ["Telegram_1.csv"],
  "634": ["Telegram_1.csv"],
  "591": ["Telegram_1.csv"],
  "524": ["Telegram_1.csv"],
  "145": ["Telegram_1.csv","Telegram_2.txt"],
  "368": ["Telegram_1.csv"],
  "321": ["Telegram_1.csv"],
  "149": ["Telegram_1.csv","Telegram_2.txt"],
  "512": ["Telegram_1.csv"],
  "054": ["Telegram_1.csv"],
  "415": ["Telegram_1.csv"],
  "442": ["Telegram_1.csv"],
  "527": ["Telegram_1.csv"],
  "529": ["Telegram_1.csv"],
  "243": ["Telegram_1.csv"],
  "254": ["Telegram_1.csv"],
  "495": ["Telegram_1.csv"],
  "153": ["Telegram_1.csv","Telegram_2.txt"],
  "898": ["Telegram_1.csv"],
  "310": ["Telegram_1.csv"],
  "361": ["Telegram_1.csv"],
  "387": ["Telegram_1.csv"],
  "159": ["Telegram_1.csv"],
  "837": ["Telegram_1.csv"],
  "345": ["Telegram_1.csv"],
  "899": ["Telegram_1.csv"],
  "765": ["Telegram_1.csv"],
  "265": ["Telegram_1.csv"],
  "218": ["Telegram_1.csv"],
  "168": ["Telegram_1.csv","Telegram_2.txt"],
  "169": ["Telegram_1.csv"],
  "890": ["Telegram_1.csv"],
  "252": ["Telegram_1.csv","Telegram_2.txt"],
  "675": ["Telegram_1.csv"],
  "377": ["Telegram_1.csv"],
  "276": ["Telegram_1.csv"],
  "355": ["Telegram_1.csv"],
  "713": ["Telegram_1.csv"],
  "802": ["Telegram_1.csv"],
  "598": ["Telegram_1.csv"],
  "578": ["Telegram_1.csv"],
  "896": ["Telegram_1.csv"],
  "211": ["Telegram_1.csv"],
  "320": ["Telegram_1.csv"],
  "260": ["Telegram_1.csv"],
  "895": ["Telegram_1.csv"],
  "188": ["Telegram_1.csv"],
  "189": ["Telegram_1.csv","Telegram_2.txt"],
  "464": ["Telegram_1.csv"],
  "779": ["Telegram_2.txt"]
}

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

executor = ThreadPoolExecutor(max_workers=2)

def clean_phone(raw: str) -> str:
    digits = re.sub(r'\D', '', raw)
    if len(digits) == 11 and digits[0] in ('7', '8'):
        return digits[1:]
    return digits

def _download_file_sync(file_id: str) -> Path | None:
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
    try:
        return await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(executor, _download_file_sync, file_id),
            timeout=300
        )
    except asyncio.TimeoutError:
        return None

def _search_in_file_sync(file_path: Path, phone_clean: str) -> dict | None:
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
    if prefix not in PHONE_INDEX:
        return "❌ Номер не найден в индексе"
    file_names = PHONE_INDEX[prefix]
    for fname in file_names:
        file_id = FILE_MAP.get(fname)
        if not file_id:
            continue
        file_path = await download_file_from_drive(file_id)
        if not file_path:
            continue
        result = await search_in_file(file_path, clean)
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
    await asyncio.get_event_loop().run_in_executor(executor, file_path.unlink, True)

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
    await asyncio.gather(
        run_web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
