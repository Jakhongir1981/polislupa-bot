"""Связь бота с Google Диском через веб-приложение Apps Script (gas/Code.gs).

1. Папка «📥 В Telegram-канал (на одобрение)»: каждые 10 минут бот проверяет новые фото/видео,
   присылает владельцу предпросмотр с кнопками ✅ / ❌; после ✅ публикует в канал и переносит файл
   в «✅ Опубликовано». Подпись — текстовый файл с тем же именем или описание файла на Диске.
2. Таблица «Заявки PolisLupa»: каждая заявка из бота и каждая публикация в канале пишутся строкой.
"""

import json
import logging
import os
from datetime import datetime

import aiohttp
from aiogram import Bot, F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

GAS_URL = os.environ.get("GAS_URL", "")
GAS_KEY = os.environ.get("GAS_KEY", "")
TG_LIMIT = 49 * 1024 * 1024
router = Router()
_cfg: dict = {}


def enabled() -> bool:
    return bool(GAS_URL and GAS_KEY)


def setup(db_func, channel_id, admin_id: int, tz) -> None:
    _cfg.update(db=db_func, channel=channel_id, admin=admin_id, tz=tz)
    with db_func() as con:
        con.execute("CREATE TABLE IF NOT EXISTS drive_items (file_id TEXT PRIMARY KEY, name TEXT, status TEXT, "
                    "tg_file TEXT, kind TEXT, caption TEXT, updated_at TEXT)")
        cols = {r[1] for r in con.execute("PRAGMA table_info(drive_items)")}
        if "ig_url" not in cols:
            con.execute("ALTER TABLE drive_items ADD COLUMN ig_url TEXT")


async def _get(params: dict) -> dict:
    async with aiohttp.ClientSession() as s:
        async with s.get(GAS_URL, params={**params, "key": GAS_KEY}, allow_redirects=True) as r:
            return json.loads(await r.text())


async def log_row(sheet: str, header: list, row: list) -> None:
    """Добавляет строку в Google-таблицу (лист sheet). Ошибки не мешают работе бота."""
    if not enabled():
        return
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(GAS_URL, data=json.dumps({"key": GAS_KEY, "sheet": sheet, "header": header, "row": row}),
                         headers={"Content-Type": "application/json"}, allow_redirects=True)
    except Exception as e:
        logging.warning("Google Таблица: %s", e)


async def _download(file_id: str) -> bytes:
    url = "https://drive.google.com/uc"
    async with aiohttp.ClientSession() as s:
        async with s.get(url, params={"export": "download", "id": file_id}) as r:
            data = await r.read()
            ctype = r.headers.get("Content-Type", "")
        if "text/html" in ctype:  # большой файл: страница подтверждения
            async with s.get("https://drive.usercontent.google.com/download",
                             params={"id": file_id, "export": "download", "confirm": "t"}) as r:
                data = await r.read()
    return data


def _status(fid: str):
    with _cfg["db"]() as con:
        return con.execute("SELECT * FROM drive_items WHERE file_id=?", (fid,)).fetchone()


def _save(fid: str, **kw) -> None:
    kw["updated_at"] = datetime.now(_cfg["tz"]).isoformat()
    with _cfg["db"]() as con:
        if _status(fid) is None:
            con.execute("INSERT INTO drive_items(file_id) VALUES (?)", (fid,))
        for k, v in kw.items():
            con.execute(f"UPDATE drive_items SET {k}=? WHERE file_id=?", (v, fid))


def _channel_kb(ig_link=None):
    import igpublish
    return igpublish.funnel_kb(ig_link)  # воронка: сайт, бот, Instagram


async def check_inbox(bot: Bot) -> None:
    if not enabled():
        return
    try:
        files = (await _get({"action": "list"})).get("files", [])
    except Exception as e:
        logging.error("Google Диск: %s", e)
        return
    for f in files:
        if _status(f["id"]) is not None:
            continue
        caption = (f.get("caption") or "").strip()[:1000]
        kind = "video" if f["mime"].startswith("video/") else "photo"
        try:
            if f.get("size", 0) > TG_LIMIT:
                await bot.send_message(_cfg["admin"], f"⚠️ Файл «{f['name']}» на Диске больше 50 МБ — Telegram такой "
                                       "не примет от бота. Сожмите его или разделите.")
                _save(f["id"], name=f["name"], status="too_big")
                continue
            data = await _download(f["id"])
            await bot.send_message(_cfg["admin"], f"📥 <b>Новый материал с Google Диска</b>\n«{f['name']}»")
            inp = BufferedInputFile(data, filename=f["name"])
            if kind == "video":
                msg = await bot.send_video(_cfg["admin"], inp, caption=caption or None, reply_markup=_channel_kb())
                tg_file = msg.video.file_id
            else:
                msg = await bot.send_photo(_cfg["admin"], inp, caption=caption or None, reply_markup=_channel_kb())
                tg_file = msg.photo[-1].file_id
            import igpublish
            ig_url = igpublish.save_upload(f"{f['id']}_{f['name']}", data) if igpublish.enabled() else None
            rows = []
            if ig_url:
                rows.append([InlineKeyboardButton(text="✅ Telegram + Instagram", callback_data=f"drv:okig:{f['id']}")])
            rows.append([InlineKeyboardButton(text="✅ Только Telegram" if ig_url else "✅ Опубликовать",
                                              callback_data=f"drv:ok:{f['id']}"),
                         InlineKeyboardButton(text="❌ Не публиковать", callback_data=f"drv:no:{f['id']}")])
            akb = InlineKeyboardMarkup(inline_keyboard=rows)
            await bot.send_message(_cfg["admin"], "☝️ Публикуем в канал?" + ("" if caption else
                                   "\n(Подписи нет — можно добавить .txt с тем же именем файла на Диск.)"),
                                   reply_markup=akb)
            _save(f["id"], name=f["name"], status="pending", tg_file=tg_file, kind=kind, caption=caption, ig_url=ig_url)
        except Exception as e:
            logging.error("Не удалось подготовить %s: %s", f["name"], e)


@router.callback_query(F.data.startswith("drv:"))
async def cb_drive(c: CallbackQuery) -> None:
    if c.from_user.id != _cfg["admin"]:
        await c.answer()
        return
    _, action, fid = c.data.split(":", 2)
    row = _status(fid)
    if not row or row["status"] != "pending":
        await c.answer("Уже обработано")
        return
    if action in ("ok", "okig"):
        send = c.bot.send_video if row["kind"] == "video" else c.bot.send_photo
        msg = await send(_cfg["channel"], row["tg_file"], caption=row["caption"] or None, reply_markup=_channel_kb())
        _save(fid, status="published")
        try:
            await _get({"action": "done", "id": fid})
        except Exception as e:
            logging.warning("Не удалось перенести файл на Диске: %s", e)
        await log_row("Публикации", ["Дата", "Источник", "Файл", "Подпись", "Сообщение в канале"],
                      [datetime.now(_cfg["tz"]).strftime("%d.%m.%Y %H:%M"), "Google Диск", row["name"],
                       row["caption"] or "", f"https://t.me/jakhongir_bakiev/{msg.message_id}"])
        await c.message.edit_text("✅ Опубликовано в Telegram. Файл перенесён в «✅ Опубликовано»."
                                  + ("\n⏳ Отправляю в Instagram…" if action == "okig" else ""))
        if action == "okig" and row["ig_url"]:
            import igpublish
            try:
                import reels
                cap = igpublish.ig_caption(row["caption"] or "")
                link = await (reels.publish_video(row["ig_url"], cap, fid) if row["kind"] == "video"
                              else reels.publish_images([row["ig_url"]], cap, fid))
                await igpublish.add_ig_button(c.bot, _cfg["channel"], msg.message_id, link)
                await c.bot.send_message(_cfg["admin"], f"📷 Вышло и в Instagram: {link}")
            except Exception as e:
                logging.error("Instagram: %s", e)
                await c.bot.send_message(_cfg["admin"], f"⚠️ В Telegram вышло, а в Instagram — нет: {e}")
    else:
        _save(fid, status="rejected")
        await c.message.edit_text("❌ Не публикуем. Файл остаётся на Диске, повторно предлагать не буду.")
    await c.answer()
