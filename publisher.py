"""Публикатор: выкладывает посты из content/queue.json в канал по расписанию.

Посты с "approval": true сначала приходят владельцу на одобрение (кнопки ✅ / ❌).
Формат записи очереди:
  id, at ("YYYY-MM-DD HH:MM", время Ташкента), approval (bool),
  text (HTML) и/или photo / video (URL или file_id), buttons [[["текст", "url"], ...]],
  poll {question, options, multiple}
"""

import json
import logging
import os
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup

QUEUE_PATH = os.path.join(os.path.dirname(__file__), "content", "queue.json")
router = Router()
_cfg: dict = {}


def setup(db_func, admin_id: int, channel_id: str, tz) -> None:
    _cfg.update(db=db_func, admin=admin_id, channel=channel_id, tz=tz)
    with db_func() as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS posts (id TEXT PRIMARY KEY, status TEXT, "
            "message_id INTEGER, updated_at TEXT)"
        )


def restore_rejected() -> int:
    with _cfg["db"]() as con:
        return con.execute("UPDATE posts SET status='approved' WHERE status='rejected'").rowcount


def _load_queue() -> list[dict]:
    try:
        with open(QUEUE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _kb(post: dict) -> InlineKeyboardMarkup | None:
    rows = post.get("buttons")
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=b[0], url=b[1]) for b in row] for row in rows
    ])


def _status(post_id: str) -> str | None:
    with _cfg["db"]() as con:
        row = con.execute("SELECT status FROM posts WHERE id=?", (post_id,)).fetchone()
    return row["status"] if row else None


def _set_status(post_id: str, status: str, message_id: int | None = None) -> None:
    with _cfg["db"]() as con:
        con.execute(
            "INSERT INTO posts(id, status, message_id, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET status=excluded.status, "
            "message_id=COALESCE(excluded.message_id, posts.message_id), updated_at=excluded.updated_at",
            (post_id, status, message_id, datetime.now(_cfg["tz"]).isoformat()),
        )


async def _send(bot: Bot, chat_id, post: dict, extra_kb: InlineKeyboardMarkup | None = None):
    kb = extra_kb or _kb(post)
    if post.get("poll"):
        p = post["poll"]
        if post.get("photo"):
            photo = post["photo"]
            if not photo.startswith("http"):
                photo = FSInputFile(os.path.join(os.path.dirname(QUEUE_PATH), photo))
            await bot.send_photo(chat_id, photo, caption=post.get("text", "")[:1024] or None)
        if "correct" in p:  # викторина: ребус с одним правильным ответом
            msg = await bot.send_poll(chat_id, p["question"], p["options"], is_anonymous=True, type="quiz",
                                      correct_option_id=p["correct"], explanation=p.get("explanation"))
        else:
            msg = await bot.send_poll(chat_id, p["question"], p["options"], is_anonymous=True,
                                      allows_multiple_answers=p.get("multiple", False))
        if extra_kb:
            await bot.send_message(chat_id, "☝️ Опрос", reply_markup=extra_kb)
        return msg
    text = post.get("text", "")
    if post.get("video"):
        return await bot.send_video(chat_id, post["video"], caption=text[:1024] or None, reply_markup=kb)
    if post.get("photo"):
        photo = post["photo"]
        if not photo.startswith("http"):
            photo = FSInputFile(os.path.join(os.path.dirname(QUEUE_PATH), photo))
        return await bot.send_photo(chat_id, photo, caption=text[:1024] or None, reply_markup=kb)
    return await bot.send_message(chat_id, text, reply_markup=kb, disable_web_page_preview=True)


async def tick(bot: Bot) -> None:
    now = datetime.now(_cfg["tz"]).replace(tzinfo=None)
    for post in _load_queue():
        pid = post["id"]
        st = _status(pid)
        at = datetime.strptime(post["at"], "%Y-%m-%d %H:%M")
        try:
            if st is None:
                if post.get("approval"):
                    rows = []
                    if post.get("photo"):
                        rows.append([InlineKeyboardButton(text="✅ Telegram + Instagram", callback_data=f"pub:okig:{pid}")])
                        rows.append([InlineKeyboardButton(text="✅ Только Telegram", callback_data=f"pub:ok:{pid}"),
                                     InlineKeyboardButton(text="❌ Отклонить", callback_data=f"pub:no:{pid}")])
                    else:
                        rows.append([InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"pub:ok:{pid}"),
                                     InlineKeyboardButton(text="❌ Отклонить", callback_data=f"pub:no:{pid}")])
                    kb = InlineKeyboardMarkup(inline_keyboard=rows)
                    await bot.send_message(
                        _cfg["admin"],
                        f"📝 <b>Пост на одобрение</b>\nПубликация: {at:%d.%m %H:%M}\n"
                        f"Правки пишите Claude в чат проекта.",
                    )
                    await _send(bot, _cfg["admin"], post, extra_kb=kb if post.get("poll") else None)
                    if not post.get("poll"):
                        await bot.send_message(_cfg["admin"], "☝️ Публикуем?", reply_markup=kb)
                    _set_status(pid, "pending")
                else:
                    _set_status(pid, "approved")
                    st = "approved"
            if st in ("approved", "approved_ig") and at <= now:
                msg = await _send(bot, _cfg["channel"], post)
                _set_status(pid, "published", msg.message_id)
                logging.info("Опубликован пост %s", pid)
                if st == "approved_ig" and post.get("photo"):
                    await _to_instagram(bot, post)
        except Exception as e:
            logging.error("Ошибка с постом %s: %s", pid, e)


async def _to_instagram(bot: Bot, post: dict) -> None:
    import igpublish
    extra = "🧩 Javobingizni izohlarda yozing 👇" if post.get("poll") else ""
    try:
        link = await igpublish.publish(igpublish.cover_url(post["photo"]),
                                       igpublish.ig_caption(post.get("text", ""), extra))
        await bot.send_message(_cfg["admin"], f"📷 Пост вышел и в Instagram: {link}")
    except Exception as e:
        logging.error("Instagram: %s", e)
        await bot.send_message(_cfg["admin"], f"⚠️ В Telegram пост вышел, а в Instagram — нет: {e}")


@router.callback_query(F.data.startswith("pub:"))
async def cb_publish(c: CallbackQuery) -> None:
    if c.from_user.id != _cfg["admin"]:
        await c.answer()
        return
    _, action, pid = c.data.split(":", 2)
    allowed = {"ok": "pending", "okig": "pending", "no": "pending", "re": "rejected"}[action]
    if _status(pid) != allowed:
        await c.answer("Уже обработано")
        return
    if action == "ok":
        _set_status(pid, "approved")
        await c.message.edit_text("✅ Одобрено — выйдет в Telegram по расписанию.")
    elif action == "okig":
        _set_status(pid, "approved_ig")
        await c.message.edit_text("✅ Одобрено — выйдет в Telegram и Instagram по расписанию.")
    elif action == "re":
        _set_status(pid, "approved")
        await c.message.edit_text("♻️ Пост восстановлен и одобрен — выйдет по расписанию.")
    else:
        _set_status(pid, "rejected")
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="♻️ Вернуть и одобрить", callback_data=f"pub:re:{pid}")]])
        await c.message.edit_text("❌ Отклонено. Напишите Claude, что изменить, или верните пост.", reply_markup=kb)
    await c.answer()
    await tick(c.bot)


from aiogram.filters import Command
from aiogram.types import Message

ICONS = {"pending": "⏳ ждёт одобрения", "approved": "✅ одобрен (Telegram)", "approved_ig": "✅ одобрен (Telegram + Instagram)", "rejected": "❌ отклонён", "published": "📢 опубликован"}


@router.message(Command("posts"))
async def cmd_posts(m: Message) -> None:
    if m.from_user.id != _cfg["admin"]:
        return
    lines = ["<b>Очередь постов:</b>"]
    for post in _load_queue():
        st = _status(post["id"])
        lines.append(f"• {post['at']} — {post['id']}: {ICONS.get(st, 'новый')}")
    await m.answer("\n".join(lines))
