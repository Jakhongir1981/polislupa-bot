"""Перенос видео из Instagram в Telegram-канал: по порядку, от самого старого к новому.

Каждый запуск публикует одно следующее видео. Расписание задаётся в bot.py (2 раза в день).
Ролики из списка IG_SKIP (коды из ссылок instagram.com/reel/<код>/) не переносятся —
например, партнёрские ролики, которые должны остаться только в Instagram.
"""

import logging
import os
import re
from datetime import datetime

import aiohttp
from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

GRAPH = "https://graph.instagram.com/v23.0"
TG_UPLOAD_LIMIT = 49 * 1024 * 1024
_cfg: dict = {}


def setup(db_func, channel_id: str, admin_id: int, tz) -> None:
    _cfg.update(db=db_func, channel=channel_id, admin=admin_id, tz=tz)
    with db_func() as con:
        con.executescript(
            "CREATE TABLE IF NOT EXISTS ig_posted (media_id TEXT PRIMARY KEY, permalink TEXT, "
            "message_id INTEGER, posted_at TEXT);"
            "CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);"
        )


def _get_token() -> str | None:
    with _cfg["db"]() as con:
        row = con.execute("SELECT v FROM kv WHERE k='ig_token'").fetchone()
    return row["v"] if row else os.environ.get("IG_TOKEN")


def _set_token(token: str) -> None:
    with _cfg["db"]() as con:
        con.execute("INSERT INTO kv(k, v) VALUES ('ig_token', ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (token,))


def _skip_codes() -> set[str]:
    return {c.strip() for c in os.environ.get("IG_SKIP", "").split(",") if c.strip()}


async def refresh_token() -> None:
    """Продлевает долгосрочный токен Instagram (живёт 60 дней); запускать раз в неделю."""
    token = _get_token()
    if not token:
        return
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{GRAPH.rsplit('/', 1)[0]}/refresh_access_token",
                         params={"grant_type": "ig_refresh_token", "access_token": token}) as r:
            data = await r.json()
    if "access_token" in data:
        _set_token(data["access_token"])
        logging.info("Токен Instagram продлён")
    else:
        logging.error("Не удалось продлить токен Instagram: %s", data)


async def _all_media(session: aiohttp.ClientSession, token: str) -> list[dict]:
    url = f"{GRAPH}/me/media"
    params = {"fields": "id,media_type,media_product_type,timestamp,permalink,media_url,caption,thumbnail_url",
              "limit": 100, "access_token": token}
    items: list[dict] = []
    while url:
        async with session.get(url, params=params) as r:
            data = await r.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message"))
        items += data.get("data", [])
        url = data.get("paging", {}).get("next")
        params = None
    return items


def _clean_caption(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"(?:^|\s)#[\wЀ-ӿ'ʻʼ]+", "", text)  # убираем хэштеги
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


# Instagram-фразы, которые в Telegram заменяем на понятные для канала
REPLACE = [
    (r"direct(?:dan|ga|da)?\s*(murojaat|yozing|yozib)", r"bot orqali \1"),
    (r"sahifamga obuna bo['’ʻ]ling", "kanalimizga obuna bo'ling"),
    (r"profilimga obuna bo['’ʻ]ling", "kanalimizga obuna bo'ling"),
    (r"(?i)link (?:in|в) bio|ссылка в (?:шапке|профиле)", "havola pastda 👇"),
    (r"(?i)пишите в директ|напишите в директ", "пишите в бот 👇"),
]

CAPTIONS_PATH = os.path.join(os.path.dirname(__file__), "content", "ig_captions.json")


def _caption_for(m: dict) -> str:
    """Описание как в Instagram; для роликов без подписи — текст редактора из ig_captions.json."""
    import json
    code = re.search(r"/(?:reel|p|tv)/([^/]+)/", m.get("permalink", ""))
    try:
        overrides = json.load(open(CAPTIONS_PATH, encoding="utf-8"))
    except FileNotFoundError:
        overrides = {}
    if code and code.group(1) in overrides:
        return overrides[code.group(1)]
    text = _clean_caption(m.get("caption"))
    for pat, rep in REPLACE:
        text = re.sub(pat, rep, text)
    return text


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def post_next_legacy(bot: Bot, preview_chat: int | None = None) -> None:
    """preview_chat: отправить следующее видео только туда (проверка), без отметки «опубликовано»."""
    token = _get_token()
    if not token:
        logging.warning("IG_TOKEN не задан — перенос видео пропущен")
        return
    with _cfg["db"]() as con:
        done = {r["media_id"] for r in con.execute("SELECT media_id FROM ig_posted")}
    skip = _skip_codes()
    async with aiohttp.ClientSession() as s:
        try:
            media = await _all_media(s, token)
        except Exception as e:
            logging.error("Instagram API: %s", e)
            await bot.send_message(_cfg["admin"], f"⚠️ Перенос видео из Instagram: ошибка доступа ({e}). Напишите Claude.")
            return
        queue = sorted((m for m in media if m.get("media_type") == "VIDEO" and m["id"] not in done
                        and not any(f"/{c}/" in m.get("permalink", "") for c in skip)),
                       key=lambda m: m["timestamp"])
        if not queue:
            logging.info("Новых видео для переноса нет")
            return
        m = queue[0]
        caption = _escape(_caption_for(m))
        footer = "\n\n📲 Savollar va arizalar — bot orqali 👇"
        caption = (caption[: 1024 - len(footer) - 3] + "…" if len(caption) + len(footer) > 1024 else caption) + footer
        kb = __import__("igpublish").funnel_kb(m["permalink"])
        try:
            video = None
            if m.get("media_url"):
                async with s.get(m["media_url"]) as r:
                    data = await r.read()
                if len(data) <= TG_UPLOAD_LIMIT:
                    video = BufferedInputFile(data, filename=f"{m['id']}.mp4")
            if video:
                msg = await bot.send_video(preview_chat or _cfg["channel"], video, caption=caption, reply_markup=kb,
                                           supports_streaming=True)
            else:  # слишком большое или без файла — публикуем ссылку
                msg = await bot.send_message(preview_chat or _cfg["channel"], caption + f"\n\n🎬 {m['permalink']}", reply_markup=kb)
        except Exception as e:
            logging.error("Не удалось опубликовать видео %s: %s", m["id"], e)
            return
    if preview_chat:
        return
    with _cfg["db"]() as con:
        con.execute("INSERT INTO ig_posted(media_id, permalink, message_id, posted_at) VALUES (?,?,?,?)",
                    (m["id"], m["permalink"], msg.message_id, datetime.now(_cfg["tz"]).isoformat()))
    logging.info("Перенесено видео %s (%s), осталось %s", m["id"], m["timestamp"], len(queue) - 1)


# ---------- Одобрение видео владельцем ----------
# 09:00 — бот присылает владельцу 2 следующих видео (на 13:00 и 20:00) с кнопками ✅ / ❌.
# В слот публикуется только одобренное видео. Отклонённое больше не предлагается.
from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router()
SLOTS = ("13:00", "20:00")


def _init_queue() -> None:
    with _cfg["db"]() as con:
        con.execute("CREATE TABLE IF NOT EXISTS ig_queue (media_id TEXT PRIMARY KEY, slot TEXT, status TEXT, "
                    "permalink TEXT, updated_at TEXT)")


def _qstatus(media_id: str):
    with _cfg["db"]() as con:
        return con.execute("SELECT * FROM ig_queue WHERE media_id=?", (media_id,)).fetchone()


def _qset(media_id: str, **kw) -> None:
    kw["updated_at"] = datetime.now(_cfg["tz"]).isoformat()
    with _cfg["db"]() as con:
        if _qstatus(media_id) is None:
            con.execute("INSERT INTO ig_queue(media_id) VALUES (?)", (media_id,))
        for k, v in kw.items():
            con.execute(f"UPDATE ig_queue SET {k}=? WHERE media_id=?", (v, media_id))


async def _candidates(session) -> list[dict]:
    token = _get_token()
    media = await _all_media(session, token)
    with _cfg["db"]() as con:
        done = {r["media_id"] for r in con.execute("SELECT media_id FROM ig_posted")}
        blocked = {r["media_id"] for r in con.execute(
            "SELECT media_id FROM ig_queue WHERE status IN ('rejected','pending','approved')")}
    skip = _skip_codes()
    return sorted((m for m in media if m.get("media_type") == "VIDEO" and m["id"] not in done | blocked
                   and not any(f"/{c}/" in m.get("permalink", "") for c in skip)), key=lambda m: m["timestamp"])


def _build(m: dict):
    caption = _escape(_caption_for(m))
    footer = "\n\n📲 Savollar va arizalar — bot orqali 👇"
    caption = (caption[: 1024 - len(footer) - 3] + "…" if len(caption) + len(footer) > 1024 else caption) + footer
    kb = __import__("igpublish").funnel_kb(m["permalink"])
    return caption, kb


async def _send_media(bot: Bot, session, chat_id, m: dict, caption: str, kb):
    data = None
    if m.get("media_url"):
        async with session.get(m["media_url"]) as r:
            data = await r.read()
    if data and len(data) <= TG_UPLOAD_LIMIT:
        return await bot.send_video(chat_id, BufferedInputFile(data, filename=f"{m['id']}.mp4"),
                                    caption=caption, reply_markup=kb, supports_streaming=True)
    return await bot.send_message(chat_id, caption + f"\n\n🎬 {m['permalink']}", reply_markup=kb)


async def prepare_day(bot: Bot) -> None:
    """Утром присылает владельцу видео на сегодняшние слоты для одобрения."""
    if not _get_token():
        return
    _init_queue()
    today = datetime.now(_cfg["tz"]).strftime("%Y-%m-%d")
    with _cfg["db"]() as con:
        taken = {r["slot"] for r in con.execute("SELECT slot FROM ig_queue WHERE slot LIKE ? AND status IN ('pending','approved')", (today + "%",))}
    free = [f"{today} {s}" for s in SLOTS if f"{today} {s}" not in taken]
    if not free:
        return
    async with aiohttp.ClientSession() as s:
        try:
            cands = await _candidates(s)
        except Exception as e:
            await bot.send_message(_cfg["admin"], f"⚠️ Instagram: ошибка доступа ({e}). Напишите Claude.")
            return
        for slot, m in zip(free, cands):
            caption, kb = _build(m)
            await bot.send_message(_cfg["admin"], f"🎬 <b>Видео на одобрение</b>\nВыйдет в канале: {slot[5:]}")
            await _send_media(bot, s, _cfg["admin"], m, caption, kb)
            akb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"igv:ok:{m['id']}"),
                InlineKeyboardButton(text="❌ Не публиковать", callback_data=f"igv:no:{m['id']}"),
            ]])
            await bot.send_message(_cfg["admin"], "☝️ Публикуем это видео?", reply_markup=akb)
            _qset(m["id"], slot=slot, status="pending", permalink=m["permalink"])


async def publish_slot(bot: Bot) -> None:
    """В 13:00 и 20:00 публикует одобренное видео этого слота."""
    _init_queue()
    now = datetime.now(_cfg["tz"])
    with _cfg["db"]() as con:
        row = con.execute("SELECT * FROM ig_queue WHERE status='approved' AND slot<=? ORDER BY slot LIMIT 1",
                          (now.strftime("%Y-%m-%d %H:%M"),)).fetchone()
    if not row:
        return
    async with aiohttp.ClientSession() as s:
        media = {m["id"]: m for m in await _all_media(s, _get_token())}
        m = media.get(row["media_id"])
        if not m:
            _qset(row["media_id"], status="gone")
            return
        caption, kb = _build(m)
        try:
            msg = await _send_media(bot, s, _cfg["channel"], m, caption, kb)
        except Exception as e:
            logging.error("Не удалось опубликовать видео %s: %s", m["id"], e)
            return
    with _cfg["db"]() as con:
        con.execute("INSERT OR IGNORE INTO ig_posted(media_id, permalink, message_id, posted_at) VALUES (?,?,?,?)",
                    (m["id"], m["permalink"], msg.message_id, now.isoformat()))
    _qset(m["id"], status="published")
    from drive import log_row
    await log_row("Публикации", ["Дата", "Источник", "Файл", "Подпись", "Сообщение в канале"],
                  [now.strftime("%d.%m.%Y %H:%M"), "Instagram", m["permalink"], caption[:300],
                   f"https://t.me/jakhongir_bakiev/{msg.message_id}"])


@router.callback_query(F.data.startswith("igv:"))
async def cb_video(c: CallbackQuery) -> None:
    if c.from_user.id != _cfg["admin"]:
        await c.answer()
        return
    _, action, mid = c.data.split(":", 2)
    row = _qstatus(mid)
    if not row or row["status"] != "pending":
        await c.answer("Уже обработано")
        return
    if action == "ok":
        _qset(mid, status="approved")
        await c.message.edit_text(f"✅ Одобрено — выйдет {row['slot'][5:]}.")
        await publish_slot(c.bot)  # если время слота уже прошло — публикуем сразу
    else:
        _qset(mid, status="rejected")
        await c.message.edit_text("❌ Это видео в канал не пойдёт. Завтра утром пришлю следующее.")
    await c.answer()
