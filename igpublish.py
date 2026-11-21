"""Публикация в Instagram через Instagram API (вход через Instagram).

Instagram забирает фото/видео по публичной ссылке, поэтому сервер бота раздаёт файлы:
  /media/img/<файл>   — обложки из content/img
  /media/up/<файл>    — материалы с Google Диска (сохраняются в /data/media)
"""

import asyncio
import logging
import os
import re

import aiohttp
from aiohttp import web

GRAPH = "https://graph.instagram.com/v23.0"
PUBLIC_URL = "https://" + os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
IMG_DIR = os.path.join(os.path.dirname(__file__), "content", "img")
UP_DIR = os.path.join(os.path.dirname(os.environ.get("DB_PATH", "data/bot.db")), "media")
os.makedirs(UP_DIR, exist_ok=True)


def enabled() -> bool:
    from igsync import _get_token
    return bool(os.environ.get("RAILWAY_PUBLIC_DOMAIN") and _get_token())


# ---------- раздача файлов ----------
EXTRA_ROUTES = []  # (method, path, handler) — добавляют другие модули (proposals.py)


async def start_web() -> None:
    app = web.Application(client_max_size=40 * 1024 * 1024)
    for method, path, handler in EXTRA_ROUTES:
        app.router.add_route(method, path, handler)
    app.router.add_static("/media/img/", IMG_DIR, show_index=False)
    app.router.add_static("/media/up/", UP_DIR, show_index=False)
    app.router.add_get("/", lambda r: web.Response(text="PolisLupa bot"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", "8080"))).start()
    logging.info("Раздача медиа запущена: %s", PUBLIC_URL)


def save_upload(name: str, data: bytes) -> str:
    """Сохраняет файл для Instagram и возвращает его публичную ссылку."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    with open(os.path.join(UP_DIR, safe), "wb") as f:
        f.write(data)
    return f"{PUBLIC_URL}/media/up/{safe}"


def cover_url(rel_path: str) -> str:
    return f"{PUBLIC_URL}/media/img/{os.path.basename(rel_path)}"


# ---------- подпись ----------
def ig_caption(html_text: str, extra: str = "") -> str:
    """Telegram-HTML → текст для Instagram (без тегов, со ссылкой «в шапке профиля»)."""
    text = re.sub(r"<[^>]+>", "", html_text or "")
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    tail = "\n\n📲 Telegram-kanal va bot — profil sarlavhasidagi havola orqali 👆"
    if extra:
        tail = "\n\n" + extra + tail
    tags = "\n\n#sugurta #страхование #polislupa #ozbekiston"
    return (text + tail + tags)[:2200]


# ---------- публикация ----------
async def _post(session, path, params):
    from igsync import _get_token
    params = {**params, "access_token": _get_token()}
    async with session.post(f"{GRAPH}/{path}", data=params) as r:
        data = await r.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    return data


async def _wait_ready(session, container_id: str, timeout: int = 300) -> None:
    from igsync import _get_token
    for _ in range(timeout // 5):
        async with session.get(f"{GRAPH}/{container_id}",
                               params={"fields": "status_code,status", "access_token": _get_token()}) as r:
            data = await r.json()
        code = data.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram не смог обработать файл: {data.get('status')}")
        await asyncio.sleep(5)
    raise RuntimeError("Instagram слишком долго обрабатывает видео")


async def publish(media_url: str, caption: str, kind: str = "photo") -> str:
    """Публикует фото или видео (Reels). Возвращает ссылку на публикацию."""
    async with aiohttp.ClientSession() as s:
        params = {"caption": caption}
        if kind == "video":
            params.update(media_type="REELS", video_url=media_url, share_to_feed="true")
        else:
            params.update(image_url=media_url)
        container = await _post(s, "me/media", params)
        await _wait_ready(s, container["id"])
        published = await _post(s, "me/media_publish", {"creation_id": container["id"]})
        from igsync import _get_token
        async with s.get(f"{GRAPH}/{published['id']}",
                         params={"fields": "permalink", "access_token": _get_token()}) as r:
            info = await r.json()
    link = info.get("permalink", "")
    logging.info("Опубликовано в Instagram: %s", link)
    return link


async def publish_carousel(urls: list[str], caption: str) -> str:
    """Карусель из 2–10 картинок."""
    from igsync import _get_token
    async with aiohttp.ClientSession() as s:
        children = []
        for u in urls[:10]:
            c = await _post(s, "me/media", {"image_url": u, "is_carousel_item": "true"})
            children.append(c["id"])
        for cid in children:
            await _wait_ready(s, cid)
        container = await _post(s, "me/media", {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption})
        await _wait_ready(s, container["id"])
        published = await _post(s, "me/media_publish", {"creation_id": container["id"]})
        async with s.get(f"{GRAPH}/{published['id']}", params={"fields": "permalink", "access_token": _get_token()}) as r:
            info = await r.json()
    return info.get("permalink", "")
