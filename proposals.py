"""Предложения от агента-аналитика контента (запускается по расписанию каждые 8 часов).

Агент присылает POST /api/proposal (с секретом PROPOSAL_KEY): тема, пост для Telegram,
обложка, слайды карусели для Instagram и статья для блога (uz/ru).
Бот присылает владельцу предложение с кнопками: 📢 Telegram, 📷 Instagram-карусель, 📝 Блог, ❌.
Одобренные статьи блога агент забирает в следующий запуск (GET /api/proposals/blog) и публикует на сайте.
"""

import base64
import json
import logging
import os
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.types import (BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           InputMediaPhoto)
from aiohttp import web

import igpublish

KEY = os.environ.get("PROPOSAL_KEY", "")
router = Router()
_cfg: dict = {}


def setup(db_func, bot: Bot, channel_id, admin_id: int, tz) -> None:
    _cfg.update(db=db_func, bot=bot, channel=channel_id, admin=admin_id, tz=tz)
    with db_func() as con:
        con.execute("CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, data TEXT, tg TEXT, ig TEXT, blog TEXT, "
                    "created_at TEXT)")
    igpublish.EXTRA_ROUTES.extend([
        ("POST", "/api/proposal", _receive),
        ("GET", "/api/proposals/blog", _blog_queue),
        ("POST", "/api/proposals/blog_done", _blog_done),
    ])


def _get(pid):
    with _cfg["db"]() as con:
        return con.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()


def _set(pid, **kw):
    with _cfg["db"]() as con:
        for k, v in kw.items():
            con.execute(f"UPDATE proposals SET {k}=? WHERE id=?", (v, pid))


def _auth(request) -> bool:
    return KEY and request.headers.get("X-Key") == KEY


async def _receive(request: web.Request) -> web.Response:
    if not _auth(request):
        return web.json_response({"error": "forbidden"}, status=403)
    p = await request.json()
    pid = p["id"][:40]
    if _get(pid):
        return web.json_response({"ok": True, "duplicate": True})
    # картинки сохраняем на сервере (Instagram забирает их по ссылке)
    urls = []
    for i, b64 in enumerate(p.get("slides", [])):
        urls.append(igpublish.save_upload(f"{pid}_slide{i + 1}.png", base64.b64decode(b64)))
    cover_url = igpublish.save_upload(f"{pid}_cover.png", base64.b64decode(p["cover"])) if p.get("cover") else None
    data = {k: v for k, v in p.items() if k not in ("slides", "cover")}
    data.update(slide_urls=urls, cover_url=cover_url)
    with _cfg["db"]() as con:
        con.execute("INSERT INTO proposals(id, data, tg, ig, blog, created_at) VALUES (?,?,?,?,?,?)",
                    (pid, json.dumps(data, ensure_ascii=False), "new", "new", "new", datetime.now(_cfg["tz"]).isoformat()))
    await _send_to_owner(pid, data, p)
    return web.json_response({"ok": True})


async def _send_to_owner(pid, data, raw) -> None:
    bot, admin = _cfg["bot"], _cfg["admin"]
    src = "\n".join(f"• {s}" for s in data.get("sources", [])[:5])
    await bot.send_message(admin, f"💡 <b>Предложение команды</b>: {data.get('topic', '')}\n"
                                  f"{data.get('why', '')}\n\n<b>Источники:</b>\n{src}", disable_web_page_preview=True)
    if raw.get("cover"):
        await bot.send_photo(admin, BufferedInputFile(base64.b64decode(raw["cover"]), "cover.png"),
                             caption=(data.get("tg_text") or "")[:1024])
    if raw.get("slides"):
        await bot.send_message(admin, "📷 Карусель для Instagram:")
        media = [InputMediaPhoto(media=BufferedInputFile(base64.b64decode(b), f"s{i}.png"))
                 for i, b in enumerate(raw["slides"][:10])]
        await bot.send_media_group(admin, media)
    if data.get("blog_title"):
        await bot.send_message(admin, f"📝 Статья для блога: <b>{data['blog_title']}</b>\n\n{(data.get('blog_summary') or '')[:800]}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 В Telegram", callback_data=f"prop:tg:{pid}"),
         InlineKeyboardButton(text="📷 В Instagram", callback_data=f"prop:ig:{pid}")],
        [InlineKeyboardButton(text="📝 На сайт (блог)", callback_data=f"prop:blog:{pid}"),
         InlineKeyboardButton(text="✅ Везде", callback_data=f"prop:all:{pid}")],
        [InlineKeyboardButton(text="❌ Отклонить всё", callback_data=f"prop:no:{pid}")],
    ])
    when = data.get("publish_at")
    await bot.send_message(admin, ("🗓 Выйдет " + when[8:10] + "." + when[5:7] + " в " + when[11:] + " после одобрения.\n" if when else "⚡ Время не задано — выйдет сразу после нажатия кнопки.\n")
                           + "☝️ Что публикуем? Можно нажать несколько кнопок по очереди.", reply_markup=kb)


async def _do_tg(bot, data) -> str:
    text = data.get("tg_text") or ""
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📝 Ariza / Заявка",
                                                                     url="https://t.me/polislupa_bot?start=tg")]])
    if data.get("cover_url"):
        path = os.path.join(igpublish.UP_DIR, os.path.basename(data["cover_url"]))
        with open(path, "rb") as f:
            msg = await bot.send_photo(_cfg["channel"], BufferedInputFile(f.read(), "cover.png"),
                                       caption=text[:1024], reply_markup=kb)
    else:
        msg = await bot.send_message(_cfg["channel"], text, reply_markup=kb)
    p = data.get("poll")
    if p:  # викторина (ребус): правильный ответ и пояснение показывает Telegram
        await bot.send_poll(_cfg["channel"], p["question"], p["options"], is_anonymous=True, type="quiz",
                            correct_option_id=p["correct"], explanation=p.get("explanation"))
    return f"https://t.me/jakhongir_bakiev/{msg.message_id}"


@router.callback_query(F.data.startswith("prop:"))
async def cb_prop(c: CallbackQuery) -> None:
    if c.from_user.id != _cfg["admin"]:
        await c.answer()
        return
    _, action, pid = c.data.split(":", 2)
    row = _get(pid)
    if not row:
        await c.answer("Предложение не найдено")
        return
    data = json.loads(row["data"])
    bot = c.bot
    done = []
    if action == "no":
        _set(pid, tg="rejected", ig="rejected", blog="rejected")
        await c.message.edit_text("❌ Предложение отклонено.")
        await c.answer()
        return
    when = data.get("publish_at")
    if when and datetime.strptime(when, "%Y-%m-%d %H:%M") > datetime.now(_cfg["tz"]).replace(tzinfo=None):
        marks = []
        if action in ("tg", "all") and row["tg"] in ("new", "scheduled"):
            _set(pid, tg="scheduled"); marks.append("Telegram")
        if action in ("ig", "all") and row["ig"] in ("new", "scheduled"):
            _set(pid, ig="scheduled"); marks.append("Instagram")
        if action in ("blog", "all") and row["blog"] == "new" and data.get("blog_title"):
            _set(pid, blog="approved"); marks.append("блог")
        await c.answer("Запланировано")
        await bot.send_message(_cfg["admin"], f"🗓 <b>{data.get('topic', '')}</b>: выйдет {when[8:10]}.{when[5:7]} в {when[11:]} — "
                                              + ", ".join(marks))
        return
    await c.answer("Принято, публикую…")
    await _publish(bot, pid, data, action, row)


async def _publish(bot, pid, data, action, row) -> None:
    done = []
    if action in ("tg", "all") and row["tg"] in ("new", "scheduled"):
        try:
            link = await _do_tg(bot, data)
            _set(pid, tg="published")
            done.append(f"📢 Telegram: {link}")
        except Exception as e:
            done.append(f"⚠️ Telegram: {e}")
    if action in ("ig", "all") and row["ig"] in ("new", "scheduled"):
        try:
            urls = data.get("slide_urls") or ([data["cover_url"]] if data.get("cover_url") else [])
            cap = igpublish.ig_caption(data.get("ig_caption") or data.get("tg_text") or "")
            link = await (igpublish.publish_carousel(urls, cap) if len(urls) > 1 else igpublish.publish(urls[0], cap))
            _set(pid, ig="published")
            done.append(f"📷 Instagram: {link}")
        except Exception as e:
            done.append(f"⚠️ Instagram: {e}")
    if action in ("blog", "all") and row["blog"] == "new" and data.get("blog_title"):
        _set(pid, blog="approved")
        done.append("📝 Блог: одобрено — статья выйдет на сайте при следующем запуске команды (до 8 часов).")
    if done:
        await bot.send_message(_cfg["admin"], f"<b>{data.get('topic', '')}</b>\n" + "\n".join(done),
                               disable_web_page_preview=True)


async def tick(bot: Bot) -> None:
    """Публикует одобренные предложения, у которых наступило время publish_at."""
    now = datetime.now(_cfg["tz"]).replace(tzinfo=None)
    with _cfg["db"]() as con:
        rows = con.execute("SELECT * FROM proposals WHERE tg='scheduled' OR ig='scheduled'").fetchall()
    for row in rows:
        data = json.loads(row["data"])
        if datetime.strptime(data["publish_at"], "%Y-%m-%d %H:%M") > now:
            continue
        action = "all" if row["tg"] == "scheduled" and row["ig"] == "scheduled" else ("tg" if row["tg"] == "scheduled" else "ig")
        await _publish(bot, row["id"], data, action, row)


async def _blog_queue(request: web.Request) -> web.Response:
    if not _auth(request):
        return web.json_response({"error": "forbidden"}, status=403)
    with _cfg["db"]() as con:
        rows = con.execute("SELECT id, data FROM proposals WHERE blog='approved'").fetchall()
    out = []
    for r in rows:
        d = json.loads(r["data"])
        out.append({"id": r["id"], "blog_posts": d.get("blog_posts", []), "cover_url": d.get("cover_url")})
    return web.json_response({"items": out})


async def _blog_done(request: web.Request) -> web.Response:
    if not _auth(request):
        return web.json_response({"error": "forbidden"}, status=403)
    p = await request.json()
    _set(p["id"], blog="published")
    links = "\n".join(p.get("links", []))
    await _cfg["bot"].send_message(_cfg["admin"], f"📝 Статья опубликована на сайте:\n{links}")
    return web.json_response({"ok": True})
