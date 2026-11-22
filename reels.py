"""Reels и сторис для Instagram из картинок постов.

Любая картинка или карусель превращается в вертикальное видео 9:16 (по 4 секунды на слайд) и выходит
как Reels; после этого бот ставит сторис-анонс «Yangi Reels — profilga oʻting» с обложкой Reels.
(Кликабельную ссылку на Reels в сторис Instagram через программу поставить не даёт.)
"""

import asyncio
import logging
import os
import subprocess
import tempfile

import imageio_ffmpeg
from PIL import Image, ImageDraw

import igpublish

W, H = 1080, 1920
SLIDE_SEC = 4
LABEL = os.path.join(igpublish.IMG_DIR, "story-label.png")


def local_path(url_or_path: str) -> str:
    """Ссылка вида …/media/up/x.png или …/media/img/x.png → файл на сервере."""
    if "/media/up/" in url_or_path:
        return os.path.join(igpublish.UP_DIR, url_or_path.split("/media/up/", 1)[1])
    if "/media/img/" in url_or_path:
        return os.path.join(igpublish.IMG_DIR, url_or_path.split("/media/img/", 1)[1])
    if not os.path.isabs(url_or_path):
        return os.path.join(os.path.dirname(__file__), url_or_path)
    return url_or_path


def _background() -> Image.Image:
    """Фирменный фон «Самарканд и золото»: тёмно-синий градиент и золотые линии."""
    bg = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(11 - 4 * t), int(31 - 10 * t), int(58 - 16 * t)))
    d.line([(80, 150), (W - 80, 150)], fill=(200, 162, 74), width=2)
    d.line([(80, H - 150), (W - 80, H - 150)], fill=(200, 162, 74), width=2)
    return bg


def _frame(img_path: str, label: bool = False) -> Image.Image:
    bg = _background()
    im = Image.open(img_path).convert("RGB")
    im = im.resize((W, round(im.height * W / im.width)))
    if im.height > H - 360:
        k = (H - 360) / im.height
        im = im.resize((round(im.width * k), H - 360))
    y = (H - im.height) // 2 - (120 if label else 0)
    bg.paste(im, ((W - im.width) // 2, y))
    if label and os.path.exists(LABEL):
        lab = Image.open(LABEL).convert("RGBA")
        bg.paste(lab, ((W - lab.width) // 2, min(H - lab.height - 60, y + im.height + 20)), lab)
    return bg


def build_reel(images: list[str], name: str) -> tuple[str, str]:
    """Собирает mp4 9:16 из картинок. Возвращает (ссылка на видео, ссылка на обложку)."""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as tmp:
        lst = []
        for i, p in enumerate(images[:10]):
            fp = os.path.join(tmp, f"f{i}.png")
            _frame(local_path(p)).save(fp)
            lst.append(fp)
        sec = SLIDE_SEC if len(lst) > 1 else 7
        with open(os.path.join(tmp, "list.txt"), "w") as f:
            for fp in lst:
                f.write(f"file '{fp}'\nduration {sec}\n")
            f.write(f"file '{lst[-1]}'\n")
        out = os.path.join(igpublish.UP_DIR, f"{name}_reel.mp4")
        subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(tmp, "list.txt"),
                        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                        "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart", out],
                       check=True, capture_output=True)
        cover = os.path.join(igpublish.UP_DIR, f"{name}_reelcover.jpg")
        Image.open(lst[0]).save(cover, quality=90)
    base = igpublish.public_base()
    return f"{base}/media/up/{os.path.basename(out)}", f"{base}/media/up/{os.path.basename(cover)}"


def build_story(image: str, name: str) -> str:
    out = os.path.join(igpublish.UP_DIR, f"{name}_story.jpg")
    _frame(local_path(image), label=True).save(out, quality=90)
    return f"{igpublish.public_base()}/media/up/{os.path.basename(out)}"


def video_frame(video_path: str, name: str) -> str:
    """Кадр из видео (для сторис к готовому Reels)."""
    out = os.path.join(igpublish.UP_DIR, f"{name}_frame.jpg")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-ss", "1", "-i", local_path(video_path), "-frames:v", "1", out],
                   check=True, capture_output=True)
    return out


async def story(image: str, name: str) -> None:
    """Сторис-анонс к новому Reels; ошибка не мешает основной публикации."""
    try:
        url = await asyncio.to_thread(build_story, image, name)
        await igpublish.publish_story(url)
    except Exception as e:
        logging.warning("Сторис не вышла: %s", e)


async def publish_images(images: list[str], caption: str, name: str) -> str:
    """Картинка или слайды → Reels + сторис-анонс. Возвращает ссылку на Reels."""
    video_url, cover = await asyncio.to_thread(build_reel, images, name)
    link = await igpublish.publish(video_url, caption, "video", cover_url=cover)
    await story(images[0], name)
    return link


async def publish_video(video_url: str, caption: str, name: str) -> str:
    """Готовое видео → Reels + сторис-анонс с кадром из видео."""
    link = await igpublish.publish(video_url, caption, "video")
    try:
        frame = await asyncio.to_thread(video_frame, video_url, name)
        await story(frame, name)
    except Exception as e:
        logging.warning("Кадр для сторис: %s", e)
    return link
