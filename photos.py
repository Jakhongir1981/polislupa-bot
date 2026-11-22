"""Тематические фото для статей: Pixabay + фирменная рамка PolisLupa.

Фото по теме (поиск по английским ключевым словам) → обложка блога и поста в Telegram 1200×630
и первый слайд Instagram 1080×1350: затемнение, тонкая золотая рамка, логотип, рубрика и заголовок.
Фото Pixabay бесплатны для коммерческого использования без указания автора.
"""

import io
import logging
import os

import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont

KEY = os.environ.get("PIXABAY_KEY", "")
FONTS = os.path.join(os.path.dirname(__file__), "content", "fonts")
NAVY = (11, 31, 58)
GOLD = (200, 162, 74)
CREAM = (246, 236, 211)


def _font(name: str, size: int, weight: str) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(os.path.join(FONTS, name), size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


async def find(query: str, orientation: str = "horizontal") -> bytes | None:
    """Лучшее фото по запросу (английские слова). None — если ключа нет или ничего не нашлось."""
    if not KEY or not query:
        return None
    params = {"key": KEY, "q": query[:100], "image_type": "photo", "orientation": orientation,
              "safesearch": "true", "min_width": "1600", "order": "popular", "per_page": "10"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40)) as s:
            async with s.get("https://pixabay.com/api/", params=params) as r:
                hits = (await r.json()).get("hits", [])
            if not hits and orientation != "all":
                return await find(query, "all")
            for h in hits[:3]:
                async with s.get(h["largeImageURL"]) as r:
                    if r.status == 200:
                        return await r.read()
    except Exception as e:
        logging.warning("Pixabay: %s", e)
    return None


def _cover_crop(im: Image.Image, w: int, h: int) -> Image.Image:
    k = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def _wrap(draw, text, font, width):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if draw.textlength(t, font=font) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def compose(photo: bytes, title: str, chip: str = "", size=(1200, 630)) -> Image.Image:
    w, h = size
    tall = h > w
    im = _cover_crop(Image.open(io.BytesIO(photo)).convert("RGB"), w, h)
    # затемнение: общее лёгкое + градиент к тёмно-синему внизу, где текст
    shade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(shade)
    start = int(h * (0.38 if tall else 0.30))
    for y in range(h):
        top = max(0, 1 - y / (h * 0.22)) * 120                       # тень под логотипом
        if y < start:
            a = 70 + top
        else:
            a = 70 + (245 - 70) * ((y - start) / (h - start)) ** 0.9   # к низу почти сплошной синий
        d.line([(0, y), (w, y)], fill=(*NAVY, int(min(a, 245))))
    im = Image.alpha_composite(im.convert("RGBA"), shade)
    d = ImageDraw.Draw(im)
    m = 26 if not tall else 30
    d.rectangle([m, m, w - m, h - m], outline=(*GOLD, 255), width=2)
    # логотип
    pad = 58 if not tall else 70
    lf = _font("Inter.ttf", 30 if not tall else 38, "Bold")
    d.text((pad, pad - 6), "Polis", font=lf, fill=CREAM)
    d.text((pad + d.textlength("Polis", font=lf), pad - 6), "Lupa", font=lf, fill=GOLD)
    # заголовок: подбираем размер, чтобы влез в 3 строки (4 — для вертикального)
    maxw = w - 2 * pad
    max_lines = 4 if tall else 3
    for fs in ((78, 72, 66, 60, 54) if tall else (58, 54, 50, 46, 42, 38)):
        tf = _font("Playfair.ttf", fs, "Bold")
        lines = _wrap(d, title, tf, maxw)
        if len(lines) <= max_lines:
            break
    lh = int(fs * 1.18)
    y = h - pad - lh * len(lines)
    for i, line in enumerate(lines):
        d.text((pad, y + i * lh), line, font=tf, fill=CREAM)
    if chip:
        cf = _font("Inter.ttf", 22 if not tall else 28, "SemiBold")
        cy = y - (40 if not tall else 52)
        d.rectangle([pad, cy - 16, pad + 56, cy - 12], fill=GOLD)
        d.text((pad, cy), chip.upper(), font=cf, fill=GOLD)
    return im.convert("RGB")


def to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=87, optimize=True, progressive=True)
    return buf.getvalue()
