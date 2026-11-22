"""Предложения от агента-аналитика контента (запускается по расписанию каждые 8 часов).

Агент присылает POST /api/proposal (с секретом PROPOSAL_KEY): тема, пост для Telegram,
обложка, слайды карусели для Instagram и статья для блога (uz/ru).
Бот присылает владельцу предложение с кнопками: 📢 Telegram, 📷 Instagram-карусель, 📝 Блог, ❌.
Воронка: при «✅ Везде» сначала выходит статья на сайте (GitHub Actions сайта каждые 5 минут забирает
GET /api/blog/pending и публикует), а пост в Telegram и карусель в Instagram выходят сразу после неё —
со ссылкой на статью. Если статья не появилась за 45 минут, посты выходят без ожидания.
"""

import base64
import json
import logging
import os
import aiohttp
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
        cols = [r[1] for r in con.execute("PRAGMA table_info(proposals)")]
        if "wait_since" not in cols:
            con.execute("ALTER TABLE proposals ADD COLUMN wait_since TEXT")
    igpublish.EXTRA_ROUTES.extend([
        ("POST", "/api/proposal", _receive),
        ("GET", "/api/proposals/blog", _blog_queue),
        ("POST", "/api/proposals/blog_done", _blog_done),
        ("GET", "/api/blog/pending", _blog_pending),  # без ключа: там только уже одобренные к публикации статьи
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


SITE = "https://polislupa.uz"
WAIT_MIN = 45


def _article_url(data):
    """Адрес статьи на сайте (узбекская версия; сайт сам переключает язык)."""
    posts = data.get("blog_posts") or []
    if not posts:
        return None
    p = next((x for x in posts if x.get("lang") == "uz"), posts[0])
    return f"{SITE}/blog/{p['slug']}/"


async def _is_live(url) -> bool:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
            async with s.get(url, allow_redirects=True) as r:
                return r.status == 200
    except Exception:
        return False


async def _do_tg(bot, data, article=None) -> str:
    text = data.get("tg_text") or ""
    rows = []
    if article:
        rows.append([InlineKeyboardButton(text="📖 Maqolani oʻqish / Читать статью", url=article)])
    rows.append([InlineKeyboardButton(text="📝 Ariza / Заявка", url="https://t.me/polislupa_bot?start=tg")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
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
        if action in ("blog", "all") and row["blog"] == "new" and _article_url(data):
            _set(pid, blog="sched_blog"); marks.append("сайт (статья выйдет первой, посты — со ссылкой на неё)")
        await c.answer("Запланировано")
        await bot.send_message(_cfg["admin"], f"🗓 <b>{data.get('topic', '')}</b>: выйдет {when[8:10]}.{when[5:7]} в {when[11:]} — "
                                              + ", ".join(marks))
        return
    article = _article_url(data)
    if action in ("blog", "all") and article and row["blog"] == "new":
        _set(pid, blog="approved")
        if action == "all":
            waiting = []
            for ch, name in (("tg", "Telegram"), ("ig", "Instagram")):
                if row[ch] == "new":
                    _set(pid, **{ch: "wait_blog"}); waiting.append(name)
            _set(pid, wait_since=datetime.now(_cfg["tz"]).replace(tzinfo=None).isoformat())
            await c.answer("Принято")
            await bot.send_message(_cfg["admin"], f"📝 <b>{data.get('topic', '')}</b>: статья уходит на сайт (5–15 мин). "
                                                  f"{' и '.join(waiting)} выйдут сразу после неё — со ссылкой на статью.")
            return
        await c.answer("Принято")
        await bot.send_message(_cfg["admin"], "📝 Статья уходит на сайт (5–15 мин), пришлю ссылку.")
        return
    await c.answer("Принято, публикую…")
    await _publish(bot, pid, data, action, _get(pid))


async def _publish(bot, pid, data, action, row) -> None:
    done = []
    article = _article_url(data) if row["blog"] in ("approved", "published") else None
    if article and row["blog"] == "approved" and not await _is_live(article):
        article = None  # статья ещё не вышла — ссылку не ставим
    if action in ("tg", "all") and row["tg"] in ("new", "scheduled", "wait_blog"):
        try:
            link = await _do_tg(bot, data, article)
            _set(pid, tg="published")
            done.append(f"📢 Telegram: {link}")
        except Exception as e:
            done.append(f"⚠️ Telegram: {e}")
    if action in ("ig", "all") and row["ig"] in ("new", "scheduled", "wait_blog"):
        try:
            urls = data.get("slide_urls") or ([data["cover_url"]] if data.get("cover_url") else [])
            cap = igpublish.ig_caption(data.get("ig_caption") or data.get("tg_text") or "")
            if article:
                cap += "\n\n📖 Toʻliq maqola — polislupa.uz (havola profilda)"
            link = await (igpublish.publish_carousel(urls, cap) if len(urls) > 1 else igpublish.publish(urls[0], cap))
            _set(pid, ig="published")
            done.append(f"📷 Instagram: {link}")
        except Exception as e:
            done.append(f"⚠️ Instagram: {e}")
    if article:
        done.append(f"📝 Сайт: {article}")
    if done:
        await bot.send_message(_cfg["admin"], f"<b>{data.get('topic', '')}</b>\n" + "\n".join(done),
                               disable_web_page_preview=True)


async def tick(bot: Bot) -> None:
    """Публикует одобренные предложения, у которых наступило время publish_at."""
    now = datetime.now(_cfg["tz"]).replace(tzinfo=None)
    with _cfg["db"]() as con:
        rows = con.execute("SELECT * FROM proposals WHERE tg='scheduled' OR ig='scheduled' OR blog='sched_blog'").fetchall()
    for row in rows:
        data = json.loads(row["data"])
        if datetime.strptime(data["publish_at"], "%Y-%m-%d %H:%M") > now:
            continue
        if row["blog"] == "sched_blog":  # время пришло: сначала статья, посты ждут её
            upd = {"blog": "approved", "wait_since": now.isoformat()}
            upd.update({ch: "wait_blog" for ch in ("tg", "ig") if row[ch] == "scheduled"})
            _set(row["id"], **upd)
            continue
        action = "all" if row["tg"] == "scheduled" and row["ig"] == "scheduled" else ("tg" if row["tg"] == "scheduled" else "ig")
        await _publish(bot, row["id"], data, action, row)
    # воронка: ждём выхода статьи на сайте, потом публикуем Telegram и Instagram со ссылкой
    with _cfg["db"]() as con:
        rows = con.execute("SELECT * FROM proposals WHERE tg='wait_blog' OR ig='wait_blog' OR blog='approved'").fetchall()
    for row in rows:
        data = json.loads(row["data"])
        article = _article_url(data)
        live = bool(article) and await _is_live(article)
        if live and row["blog"] == "approved":
            _set(row["id"], blog="published")
            if "wait_blog" not in (row["tg"], row["ig"]):
                await bot.send_message(_cfg["admin"], f"📝 Статья опубликована на сайте:\n{article}")
        waiting = [ch for ch in ("tg", "ig") if row[ch] == "wait_blog"]
        if not waiting:
            continue
        since = datetime.fromisoformat(row["wait_since"]) if row["wait_since"] else now
        if live or (now - since).total_seconds() > WAIT_MIN * 60:
            action = "all" if len(waiting) == 2 else waiting[0]
            await _publish(bot, row["id"], data, action, _get(row["id"]))


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


async def _blog_pending(request: web.Request) -> web.Response:
    """Одобренные статьи, которых ещё нет на сайте — их забирает GitHub Actions сайта."""
    with _cfg["db"]() as con:
        rows = con.execute("SELECT id, data FROM proposals WHERE blog='approved'").fetchall()
    out = [{"id": r["id"], "blog_posts": json.loads(r["data"]).get("blog_posts", []),
            "cover_url": json.loads(r["data"]).get("cover_url")} for r in rows]
    return web.json_response({"items": out})


async def _blog_done(request: web.Request) -> web.Response:
    if not _auth(request):
        return web.json_response({"error": "forbidden"}, status=403)
    p = await request.json()
    _set(p["id"], blog="published")
    links = "\n".join(p.get("links", []))
    await _cfg["bot"].send_message(_cfg["admin"], f"📝 Статья опубликована на сайте:\n{links}")
    return web.json_response({"ok": True})
