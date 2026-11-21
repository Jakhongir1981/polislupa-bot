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


async def post_next(bot: Bot, preview_chat: int | None = None) -> None:
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
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📝 Ariza / Заявка", url="https://t.me/polislupa_bot?start=tg"),
            InlineKeyboardButton(text="📷 Instagram", url=m["permalink"]),
        ]])
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
