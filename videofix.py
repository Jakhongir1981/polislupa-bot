"""Видео для Telegram: правильный поворот и пропорции, быстрый старт, размеры и обложка.

Без width/height Telegram иногда показывает вертикальное видео широким. Здесь видео перекодируется
(ffmpeg сам применяет поворот с телефона), а размеры, длительность и кадр-обложка передаются явно.
"""

import os
import re
import subprocess
import tempfile

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()


def _probe(path: str) -> tuple[int, int, int]:
    out = subprocess.run([FF, "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", out)
    d = re.search(r"Duration: (\d+):(\d+):(\d+)", out)
    w, h = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    dur = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + int(d.group(3)) if d else 0
    return w, h, dur


def prepare(src: str) -> dict:
    """Возвращает {'path', 'width', 'height', 'duration', 'thumb'} — готово для send_video."""
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "video.mp4")
    subprocess.run([FF, "-y", "-i", src, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-metadata:s:v", "rotate=0", out],
                   check=True, capture_output=True)
    w, h, dur = _probe(out)
    thumb = os.path.join(tmp, "thumb.jpg")
    subprocess.run([FF, "-y", "-ss", "1", "-i", out, "-frames:v", "1", "-vf", "scale=320:-2", thumb],
                   capture_output=True)
    return {"path": out, "width": w, "height": h, "duration": dur, "thumb": thumb if os.path.exists(thumb) else None}


async def send(bot, chat_id, src: str, caption=None, reply_markup=None):
    from aiogram.types import FSInputFile
    v = prepare(src)
    return await bot.send_video(chat_id, FSInputFile(v["path"]), width=v["width"], height=v["height"],
                                duration=v["duration"], thumbnail=FSInputFile(v["thumb"]) if v["thumb"] else None,
                                supports_streaming=True, caption=caption, reply_markup=reply_markup)
