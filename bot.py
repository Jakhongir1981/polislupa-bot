"""PolisLupa — бот заявок для Telegram-канала, Instagram и сайта.

Источник заявки передаётся в ссылке: t.me/<bot>?start=ig | tg | site | ads | blog
Любой другой код после start= (например p_ali) считается партнёрским и сохраняется как есть.
"""

import asyncio
import logging
import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandObject, CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import igsync
import publisher
from texts import PRODUCT_NAMES, SOURCE_NAMES, t

# ---------- Настройки (из переменных окружения) ----------
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])          # куда приходят заявки (ваш личный ID или группа)
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")              # @username канала или -100...
CHANNEL_URL = os.environ.get("CHANNEL_URL", "")            # https://t.me/...
REMIND_DAYS = int(os.environ.get("REMIND_DAYS", "30"))
DB_PATH = os.environ.get("DB_PATH", "data/bot.db")
TZ = ZoneInfo("Asia/Tashkent")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
router = Router()


# ---------- База данных ----------
def db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT, name TEXT, lang TEXT,
                source TEXT, phone TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, product TEXT, details TEXT, phone TEXT,
                source TEXT, policy_end TEXT, reminded INTEGER DEFAULT 0,
                created_at TEXT
            );
            """
        )


def upsert_user(m: Message, source: str | None = None) -> None:
    u = m.from_user
    with db() as con:
        row = con.execute("SELECT source FROM users WHERE user_id=?", (u.id,)).fetchone()
        if row is None:
            con.execute(
                "INSERT INTO users(user_id, username, name, source, created_at) VALUES (?,?,?,?,?)",
                (u.id, u.username, u.full_name, source or "direct", datetime.now(TZ).isoformat()),
            )
        elif source and row["source"] in (None, "direct"):
            con.execute("UPDATE users SET source=? WHERE user_id=?", (source, u.id))


def get_user(user_id: int) -> sqlite3.Row | None:
    with db() as con:
        return con.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def user_lang(user_id: int) -> str:
    row = get_user(user_id)
    return row["lang"] if row and row["lang"] else "ru"


def set_lang(user_id: int, lang: str) -> None:
    with db() as con:
        con.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))


# ---------- Онлайн-оформление ----------
# Продукты, которые клиент оформляет и оплачивает сам по агентской ссылке (калькулятор gross.uz).
# Чтобы подключить новый продукт: добавьте строку сюда и кнопку в texts.py.
PRODUCT_LINKS = {
    "osago": "https://gross.uz/agent/mirzo_ulugbek/osago",
    "kasko": "https://gross.uz/agent/mirzo_ulugbek/kasko",
    "travel": "https://gross.uz/agent/mirzo_ulugbek/travel",
}


# ---------- Клавиатуры ----------
def kb_lang() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
    ]])


def kb_menu(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=t("btn_osago", lang), url=PRODUCT_LINKS["osago"])],
        [InlineKeyboardButton(text=t("btn_kasko", lang), url=PRODUCT_LINKS["kasko"])],
        [InlineKeyboardButton(text=t("btn_travel", lang), url=PRODUCT_LINKS["travel"])],
        [InlineKeyboardButton(text=t("btn_property", lang), callback_data="p:property")],
        [InlineKeyboardButton(text=t("btn_health", lang), callback_data="p:health")],
        [InlineKeyboardButton(text=t("btn_business", lang), callback_data="p:business")],
        [InlineKeyboardButton(text=t("btn_other", lang), callback_data="p:other")],
        [InlineKeyboardButton(text=t("btn_review", lang), callback_data="p:review")],
        [InlineKeyboardButton(text=t("btn_question", lang), callback_data="p:question")],
        [InlineKeyboardButton(text=t("btn_checklist", lang), callback_data="checklist")],
    ]
    last = [InlineKeyboardButton(text=t("btn_lang", lang), callback_data="chlang")]
    if CHANNEL_URL:
        last.insert(0, InlineKeyboardButton(text=t("btn_channel", lang), url=CHANNEL_URL))
    rows.append(last)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_cancel(lang: str, extra: list[str] | None = None) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=x)] for x in (extra or [])]
    rows.append([KeyboardButton(text=t("btn_cancel", lang))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def kb_phone(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("btn_share_phone", lang), request_contact=True)],
                  [KeyboardButton(text=t("btn_cancel", lang))]],
        resize_keyboard=True,
    )


# ---------- Состояния анкеты ----------
class Form(StatesGroup):
    osago_car = State()
    osago_end = State()
    kasko_car = State()
    kasko_value = State()
    travel_country = State()
    travel_dates = State()
    travel_people = State()
    property_obj = State()
    property_value = State()
    health_type = State()
    health_who = State()
    biz_company = State()
    biz_need = State()
    biz_contact = State()
    other = State()
    review_files = State()
    question = State()
    phone = State()


async def show_menu(m: Message, lang: str) -> None:
    await m.answer("👇", reply_markup=ReplyKeyboardRemove())
    await m.answer(t("welcome", lang), reply_markup=kb_menu(lang))


# ---------- Старт и язык ----------
@router.message(CommandStart())
async def cmd_start(m: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    source = (command.args or "").strip()[:32] or None
    upsert_user(m, source)
    row = get_user(m.from_user.id)
    if row and row["lang"]:
        await show_menu(m, row["lang"])
        return
    await m.answer(t("choose_lang", "ru"), reply_markup=kb_lang())


@router.callback_query(F.data == "chlang")
async def cb_chlang(c: CallbackQuery) -> None:
    await c.message.answer(t("choose_lang", "ru"), reply_markup=kb_lang())
    await c.answer()


@router.callback_query(F.data.startswith("lang:"))
async def cb_lang(c: CallbackQuery, state: FSMContext) -> None:
    lang = c.data.split(":")[1]
    set_lang(c.from_user.id, lang)
    await state.clear()
    await c.message.answer(t("welcome", lang), reply_markup=kb_menu(lang))
    await c.answer()


@router.message(Command("menu"))
async def cmd_menu(m: Message, state: FSMContext) -> None:
    await state.clear()
    upsert_user(m)
    await show_menu(m, user_lang(m.from_user.id))


@router.message(F.text.in_({"↩️ В меню", "↩️ Menyuga", "↩️ Menu"}))
async def back_to_menu(m: Message, state: FSMContext) -> None:
    await state.clear()
    await show_menu(m, user_lang(m.from_user.id))


# ---------- Выбор продукта ----------
@router.callback_query(F.data.startswith("p:"))
async def cb_product(c: CallbackQuery, state: FSMContext) -> None:
    product = c.data.split(":")[1]
    lang = user_lang(c.from_user.id)
    await state.clear()
    await state.update_data(product=product, details=[], files=[])
    first = {
        "osago": (Form.osago_car, "osago_car", None),
        "kasko": (Form.kasko_car, "kasko_car", None),
        "travel": (Form.travel_country, "travel_country", None),
        "review": (Form.review_files, "review_upload", [t("btn_done", lang)]),
        "question": (Form.question, "question_text", None),
        "property": (Form.property_obj, "property_obj", None),
        "health": (Form.health_type, "health_type", None),
        "business": (Form.biz_company, "biz_company", None),
        "other": (Form.other, "other_text", None),
    }[product]
    await state.set_state(first[0])
    await c.message.answer(t(first[1], lang), reply_markup=kb_cancel(lang, first[2]))
    await c.answer()


async def add_detail(state: FSMContext, label: str, value: str) -> None:
    data = await state.get_data()
    details = data.get("details", [])
    details.append(f"{label}: {value}")
    await state.update_data(details=details)


async def ask_phone(m: Message, state: FSMContext, lang: str) -> None:
    row = get_user(m.from_user.id)
    if row and row["phone"]:
        await finish_lead(m, state, lang, row["phone"])
        return
    await state.set_state(Form.phone)
    await m.answer(t("ask_phone", lang), reply_markup=kb_phone(lang))


# ОСАГО
@router.message(Form.osago_car, F.text)
async def osago_car(m: Message, state: FSMContext) -> None:
    lang = user_lang(m.from_user.id)
    await add_detail(state, "Авто", m.text)
    await state.set_state(Form.osago_end)
    await m.answer(t("osago_end", lang), reply_markup=kb_cancel(lang, [t("btn_no_policy", lang)]))


def parse_date(s: str) -> date | None:
    s = s.strip().replace("/", ".").replace("-", ".")
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


@router.message(Form.osago_end, F.text)
async def osago_end(m: Message, state: FSMContext) -> None:
    lang = user_lang(m.from_user.id)
    if m.text in {"Полиса нет", "Polis yo'q", "No policy yet"}:
        await add_detail(state, "Текущий полис", "нет")
    else:
        d = parse_date(m.text)
        if not d:
            await m.answer(t("bad_date", lang))
            return
        await state.update_data(policy_end=d.isoformat())
        await add_detail(state, "Полис до", d.strftime("%d.%m.%Y"))
    await ask_phone(m, state, lang)


# КАСКО
@router.message(Form.kasko_car, F.text)
async def kasko_car(m: Message, state: FSMContext) -> None:
    lang = user_lang(m.from_user.id)
    await add_detail(state, "Авто", m.text)
    await state.set_state(Form.kasko_value)
    await m.answer(t("kasko_value", lang))


@router.message(Form.kasko_value, F.text)
async def kasko_value(m: Message, state: FSMContext) -> None:
    lang = user_lang(m.from_user.id)
    await add_detail(state, "Стоимость авто", m.text)
    await ask_phone(m, state, lang)


# Путешествие
@router.message(Form.travel_country, F.text)
async def travel_country(m: Message, state: FSMContext) -> None:
    lang = user_lang(m.from_user.id)
    await add_detail(state, "Страна", m.text)
    await state.set_state(Form.travel_dates)
    await m.answer(t("travel_dates", lang))


@router.message(Form.travel_dates, F.text)
async def travel_dates(m: Message, state: FSMContext) -> None:
    lang = user_lang(m.from_user.id)
    await add_detail(state, "Даты", m.text)
    await state.set_state(Form.travel_people)
    await m.answer(t("travel_people", lang))


@router.message(Form.travel_people, F.text)
async def travel_people(m: Message, state: FSMContext) -> None:
    lang = user_lang(m.from_user.id)
    await add_detail(state, "Путешественники", m.text)
    await ask_phone(m, state, lang)



# Универсальные шаги анкеты: состояние -> (подпись в заявке, следующее состояние, ключ вопроса)
STEPS = {
    Form.property_obj.state: ("Объект", Form.property_value, "property_value"),
    Form.property_value.state: ("Город и стоимость", None, None),
    Form.health_type.state: ("Вид", Form.health_who, "health_who"),
    Form.health_who.state: ("Кого страхуем", None, None),
    Form.biz_company.state: ("Компания и сфера", Form.biz_need, "biz_need"),
    Form.biz_need.state: ("Что страхуем", Form.biz_contact, "biz_contact"),
    Form.biz_contact.state: ("Контактное лицо", None, None),
    Form.other.state: ("Запрос", None, None),
}


@router.message(StateFilter(*STEPS.keys()), F.text)
async def generic_step(m: Message, state: FSMContext) -> None:
    lang = user_lang(m.from_user.id)
    label, nxt, question_key = STEPS[await state.get_state()]
    await add_detail(state, label, m.text)
    if nxt is None:
        await ask_phone(m, state, lang)
    else:
        await state.set_state(nxt)
        await m.answer(t(question_key, lang))

# Разбор полиса
@router.message(Form.review_files, F.photo | F.document)
async def review_file(m: Message, state: FSMContext) -> None:
    lang = user_lang(m.from_user.id)
    data = await state.get_data()
    files = data.get("files", [])
    if m.photo:
        files.append(("photo", m.photo[-1].file_id))
    else:
        files.append(("document", m.document.file_id))
    await state.update_data(files=files)
    await m.answer(t("review_got", lang))


@router.message(Form.review_files, F.text.in_({"✅ Готово", "✅ Tayyor", "✅ Done"}))
async def review_done(m: Message, state: FSMContext) -> None:
    lang = user_lang(m.from_user.id)
    data = await state.get_data()
    if not data.get("files"):
        await m.answer(t("review_empty", lang))
        return
    await add_detail(state, "Файлов", str(len(data["files"])))
    await ask_phone(m, state, lang)


# Вопрос эксперту
@router.message(Form.question, F.text)
async def question(m: Message, state: FSMContext) -> None:
    lang = user_lang(m.from_user.id)
    await add_detail(state, "Вопрос", m.text)
    await ask_phone(m, state, lang)


# Телефон
PHONE_RE = re.compile(r"^\+?\d[\d\s\-()]{7,18}$")


@router.message(Form.phone, F.contact)
async def phone_contact(m: Message, state: FSMContext) -> None:
    await save_phone_and_finish(m, state, m.contact.phone_number)


@router.message(Form.phone, F.text)
async def phone_text(m: Message, state: FSMContext) -> None:
    if not PHONE_RE.match(m.text.strip()):
        await m.answer(t("bad_phone", user_lang(m.from_user.id)))
        return
    await save_phone_and_finish(m, state, m.text.strip())


async def save_phone_and_finish(m: Message, state: FSMContext, phone: str) -> None:
    with db() as con:
        con.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, m.from_user.id))
    await finish_lead(m, state, user_lang(m.from_user.id), phone)


async def finish_lead(m: Message, state: FSMContext, lang: str, phone: str) -> None:
    data = await state.get_data()
    product = data.get("product", "question")
    row = get_user(m.from_user.id)
    source = row["source"] if row else "direct"
    details = "\n".join(data.get("details", []))
    with db() as con:
        cur = con.execute(
            "INSERT INTO leads(user_id, product, details, phone, source, policy_end, created_at) VALUES (?,?,?,?,?,?,?)",
            (m.from_user.id, product, details, phone, source, data.get("policy_end"), datetime.now(TZ).isoformat()),
        )
        lead_id = cur.lastrowid
    await notify_admin(m.bot, lead_id, m.from_user, product, details, phone, source, lang, data.get("files", []))
    await state.clear()
    await m.answer(t("thanks", lang), reply_markup=ReplyKeyboardRemove())
    await m.answer("👇", reply_markup=kb_menu(lang))


async def notify_admin(bot: Bot, lead_id, user, product, details, phone, source, lang, files) -> None:
    src = SOURCE_NAMES.get(source, f"Партнёр/другое: {source}")
    who = f"@{user.username}" if user.username else user.full_name
    text = (
        f"🆕 <b>Заявка #{lead_id}: {PRODUCT_NAMES.get(product, product)}</b>\n"
        f"👤 {who} (id {user.id}), язык: {lang}\n"
        f"📞 {phone}\n"
        f"📍 Источник: {src}\n\n{details}"
    )
    try:
        await bot.send_message(ADMIN_CHAT_ID, text)
        for kind, fid in files:
            if kind == "photo":
                await bot.send_photo(ADMIN_CHAT_ID, fid, caption=f"Заявка #{lead_id}")
            else:
                await bot.send_document(ADMIN_CHAT_ID, fid, caption=f"Заявка #{lead_id}")
    except Exception as e:  # владелец ещё не нажал /start — заявка сохранена в базе
        logging.error("Не удалось отправить заявку #%s владельцу: %s", lead_id, e)


# ---------- Чек-лист за подписку ----------
async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if not CHANNEL_ID:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in {"member", "administrator", "creator"}
    except Exception as e:  # бот не админ канала или канал не найден
        logging.warning("Проверка подписки не удалась: %s", e)
        return True


@router.callback_query(F.data.in_({"checklist", "checksub"}))
async def cb_checklist(c: CallbackQuery) -> None:
    lang = user_lang(c.from_user.id)
    if await is_subscribed(c.bot, c.from_user.id):
        await c.message.answer(t("checklist", lang), reply_markup=kb_menu(lang))
    elif c.data == "checksub":
        await c.answer(t("still_not_sub", lang), show_alert=True)
        return
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_subscribe", lang), url=CHANNEL_URL or "https://t.me")],
            [InlineKeyboardButton(text=t("btn_check_sub", lang), callback_data="checksub")],
        ])
        await c.message.answer(t("need_sub", lang), reply_markup=kb)
    await c.answer()


# ---------- Напоминания о продлении ----------
async def send_reminders(bot: Bot) -> None:
    target = (datetime.now(TZ).date() + timedelta(days=REMIND_DAYS)).isoformat()
    with db() as con:
        rows = con.execute(
            "SELECT l.id, l.user_id, l.policy_end, u.lang FROM leads l JOIN users u USING(user_id) "
            "WHERE l.policy_end IS NOT NULL AND l.policy_end<=? AND l.reminded=0",
            (target,),
        ).fetchall()
    for r in rows:
        lang = r["lang"] or "ru"
        end = date.fromisoformat(r["policy_end"])
        if end < datetime.now(TZ).date():
            with db() as con:
                con.execute("UPDATE leads SET reminded=1 WHERE id=?", (r["id"],))
            continue
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t("btn_renew", lang), url=PRODUCT_LINKS["osago"])]])
        try:
            await bot.send_message(r["user_id"], t("renew_reminder", lang).format(date=end.strftime("%d.%m.%Y")), reply_markup=kb)
        except Exception as e:
            logging.warning("Не удалось отправить напоминание %s: %s", r["user_id"], e)
        with db() as con:
            con.execute("UPDATE leads SET reminded=1 WHERE id=?", (r["id"],))


@router.callback_query(F.data.startswith("renew:"))
async def cb_renew(c: CallbackQuery) -> None:
    lang = user_lang(c.from_user.id)
    row = get_user(c.from_user.id)
    phone = row["phone"] if row else "—"
    old_id = c.data.split(":")[1]
    with db() as con:
        cur = con.execute(
            "INSERT INTO leads(user_id, product, details, phone, source, created_at) VALUES (?,?,?,?,?,?)",
            (c.from_user.id, "renew", f"Продление по заявке #{old_id}", phone, "renewal", datetime.now(TZ).isoformat()),
        )
    await notify_admin(c.bot, cur.lastrowid, c.from_user, "renew", f"Продление по заявке #{old_id}", phone, "renewal", lang, [])
    await c.message.answer(t("renew_ok", lang))
    await c.answer()


# ---------- Служебные команды для владельца ----------
@router.message(Command("myid"))
async def cmd_myid(m: Message) -> None:
    await m.answer(f"Ваш ID: <code>{m.from_user.id}</code>\nID этого чата: <code>{m.chat.id}</code>")


@router.message(Command("stats"))
async def cmd_stats(m: Message) -> None:
    if m.chat.id != ADMIN_CHAT_ID:
        return
    with db() as con:
        users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        week = (datetime.now(TZ) - timedelta(days=7)).isoformat()
        by_src = con.execute(
            "SELECT source, COUNT(*) n FROM leads WHERE created_at>=? GROUP BY source ORDER BY n DESC", (week,)
        ).fetchall()
        by_prod = con.execute(
            "SELECT product, COUNT(*) n FROM leads WHERE created_at>=? GROUP BY product ORDER BY n DESC", (week,)
        ).fetchall()
    lines = [f"👥 Пользователей бота: {users}", "", "<b>Заявки за 7 дней по источникам:</b>"]
    lines += [f"• {SOURCE_NAMES.get(r['source'], r['source'])}: {r['n']}" for r in by_src] or ["• пока нет"]
    lines += ["", "<b>По продуктам:</b>"]
    lines += [f"• {PRODUCT_NAMES.get(r['product'], r['product'])}: {r['n']}" for r in by_prod] or ["• пока нет"]
    await m.answer("\n".join(lines))


@router.message(Command("ig"))
async def cmd_ig(m: Message) -> None:
    if m.chat.id != ADMIN_CHAT_ID:
        return
    with db() as con:
        n = con.execute("SELECT COUNT(*) FROM ig_posted").fetchone()[0]
        last = con.execute("SELECT permalink, posted_at FROM ig_posted ORDER BY posted_at DESC LIMIT 1").fetchone()
    txt = f"🎬 Перенесено видео из Instagram: {n}\nРасписание: 13:00 и 20:00 каждый день"
    if last:
        txt += f"\nПоследнее: {last['permalink']}"
    await m.answer(txt)


# ---------- Запуск ----------
async def main() -> None:
    init_db()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(publisher.router)
    dp.include_router(igsync.router)
    dp.include_router(router)
    publisher.setup(db, ADMIN_CHAT_ID, CHANNEL_ID, TZ)
    igsync.setup(db, CHANNEL_ID, ADMIN_CHAT_ID, TZ)
    if os.environ.get("RESTORE_REJECTED") == "1":
        logging.info("Восстановлено отклонённых постов: %s", publisher.restore_rejected())
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(send_reminders, "cron", hour=10, minute=0, args=[bot])
    scheduler.add_job(publisher.tick, "interval", minutes=1, args=[bot])
    scheduler.add_job(igsync.prepare_day, "cron", hour=9, minute=0, args=[bot])  # видео на одобрение
    for hour in (13, 20):  # два видео из Instagram в день, только одобренные
        scheduler.add_job(igsync.publish_slot, "cron", hour=hour, minute=0, args=[bot])
    scheduler.add_job(igsync.refresh_token, "cron", day_of_week="mon", hour=4, minute=0)
    scheduler.start()
    if os.environ.get("IG_PREPARE_ON_START") == "1":
        await igsync.prepare_day(bot)
    if os.environ.get("IG_TEST_ON_START") == "1":
        await bot.send_message(ADMIN_CHAT_ID, "👀 Тест: так будут выходить видео из Instagram в канале (это предпросмотр, в канал не отправлено).")
        await igsync.post_next_legacy(bot, preview_chat=ADMIN_CHAT_ID)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
