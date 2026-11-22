"""Публикация на странице Facebook «Jakhongir Bakiev».

Reels — то же видео, что уходит в Instagram; пост со ссылкой на статью — ссылка в Facebook кликабельна,
превью берётся из обложки статьи на сайте. Ключ страницы бессрочный (env FB_PAGE_TOKEN).
"""

import asyncio
import logging
import os

import aiohttp

GRAPH = "https://graph.facebook.com/v23.0"
PAGE_ID = os.environ.get("FB_PAGE_ID", "1488661464320029")
TOKEN = os.environ.get("FB_PAGE_TOKEN", "")


def enabled() -> bool:
    return bool(TOKEN)


async def _call(s, method, path, **params):
    params["access_token"] = TOKEN
    async with s.request(method, f"{GRAPH}/{path}", data=params if method == "POST" else None,
                         params=params if method == "GET" else None) as r:
        data = await r.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    return data


async def publish_reel(video_url: str, description: str) -> str:
    """Reels на странице из готового mp4 по ссылке. Возвращает ссылку на Reels."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as s:
        start = await _call(s, "POST", f"{PAGE_ID}/video_reels", upload_phase="start")
        vid = start["video_id"]
        async with s.post(f"https://rupload.facebook.com/video-upload/v23.0/{vid}",
                          headers={"Authorization": f"OAuth {TOKEN}", "file_url": video_url}) as r:
            up = await r.json()
        if not up.get("success"):
            raise RuntimeError(f"Facebook не принял видео: {up}")
        await _call(s, "POST", f"{PAGE_ID}/video_reels", upload_phase="finish", video_id=vid,
                    video_state="PUBLISHED", description=description[:2200])
        for _ in range(60):  # ждём обработку
            st = await _call(s, "GET", vid, fields="status")
            phase = (st.get("status") or {}).get("video_status")
            if phase in ("ready", "published"):
                break
            if phase == "error":
                raise RuntimeError(f"Facebook не смог обработать видео: {st}")
            await asyncio.sleep(5)
    link = f"https://www.facebook.com/reel/{vid}"
    logging.info("Опубликовано в Facebook: %s", link)
    return link


async def post_link(message: str, link: str) -> str:
    """Пост со ссылкой (кликабельной) на статью; превью — обложка статьи."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
        res = await _call(s, "POST", f"{PAGE_ID}/feed", message=message[:5000], link=link)
    pid = res["id"].split("_")[-1]
    return f"https://www.facebook.com/{PAGE_ID}/posts/{pid}"


async def post_photo(image_url: str, caption: str) -> str:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as s:
        res = await _call(s, "POST", f"{PAGE_ID}/photos", url=image_url, caption=caption[:5000])
    return f"https://www.facebook.com/{res.get('post_id', res['id']).replace('_', '/posts/')}"
