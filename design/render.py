"""Рендер фирменных обложек PolisLupa (1080x1080) через Chrome."""
import json, sys, pathlib, re, base64
from playwright.sync_api import sync_playwright

ICONS = pathlib.Path(__file__).parent / "node_modules/lucide-static/icons"
OUT = pathlib.Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

THEMES = {
    "auto":     ("#0B1B3A", "#1E4FD8", "#5AA9FF"),
    "property": ("#0E2A2A", "#0F8F7A", "#5FE3C8"),
    "biz":      ("#151530", "#5B3FD9", "#A99BFF"),
    "travel":   ("#0A2240", "#0E7FC2", "#7FD3FF"),
    "health":   ("#2A0F1E", "#C2185B", "#FF8FB8"),
    "warn":     ("#2A1A06", "#C77A0A", "#FFC861"),
    "shield":   ("#0B2318", "#1E9E5A", "#7EF0B0"),
    "poll":     ("#1A1530", "#7B3FE4", "#C9A6FF"),
}

TPL = """<html><head><style>
@font-face{font-family:PF;font-weight:700;src:url('file://{BASE}/node_modules/@fontsource/playfair-display/files/playfair-display-latin-700-normal.woff2')}
@font-face{font-family:PF;font-weight:700;src:url('file://{BASE}/node_modules/@fontsource/playfair-display/files/playfair-display-latin-ext-700-normal.woff2');unicode-range:U+0100-024F,U+02BB-02BC,U+1E00-1EFF}
@font-face{font-family:PF;font-weight:700;src:url('file://{BASE}/node_modules/@fontsource/playfair-display/files/playfair-display-cyrillic-700-normal.woff2');unicode-range:U+0400-04FF}
@font-face{font-family:IN;font-weight:400;src:url('file://{BASE}/node_modules/@fontsource/inter/files/inter-latin-400-normal.woff2')}
@font-face{font-family:IN;font-weight:400;src:url('file://{BASE}/node_modules/@fontsource/inter/files/inter-latin-ext-400-normal.woff2');unicode-range:U+0100-024F,U+02BB-02BC,U+1E00-1EFF}
@font-face{font-family:IN;font-weight:400;src:url('file://{BASE}/node_modules/@fontsource/inter/files/inter-cyrillic-400-normal.woff2');unicode-range:U+0400-04FF}
@font-face{font-family:IN;font-weight:600;src:url('file://{BASE}/node_modules/@fontsource/inter/files/inter-latin-600-normal.woff2')}
@font-face{font-family:IN;font-weight:600;src:url('file://{BASE}/node_modules/@fontsource/inter/files/inter-latin-ext-600-normal.woff2');unicode-range:U+0100-024F,U+02BB-02BC,U+1E00-1EFF}
@font-face{font-family:IN;font-weight:600;src:url('file://{BASE}/node_modules/@fontsource/inter/files/inter-cyrillic-600-normal.woff2');unicode-range:U+0400-04FF}
@font-face{font-family:IN;font-weight:800;src:url('file://{BASE}/node_modules/@fontsource/inter/files/inter-latin-800-normal.woff2')}
@font-face{font-family:IN;font-weight:800;src:url('file://{BASE}/node_modules/@fontsource/inter/files/inter-latin-ext-800-normal.woff2');unicode-range:U+0100-024F,U+02BB-02BC,U+1E00-1EFF}
@font-face{font-family:IN;font-weight:800;src:url('file://{BASE}/node_modules/@fontsource/inter/files/inter-cyrillic-800-normal.woff2');unicode-range:U+0400-04FF}
*{margin:0;box-sizing:border-box}
body{width:1080px;height:1080px;font-family:IN,sans-serif;color:#f0dfb4;overflow:hidden;
 background:radial-gradient(circle at 76% 28%, #2ba6b833 0%, transparent 40%), url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><g fill='none' stroke='%23c8a24a' stroke-opacity='0.08' stroke-width='1.2'><rect x='35' y='35' width='50' height='50'/><rect x='35' y='35' width='50' height='50' transform='rotate(45 60 60)'/><circle cx='60' cy='60' r='12'/><path d='M0 0L35 35M120 0L85 35M0 120L35 85M120 120L85 85'/></g></svg>"), linear-gradient(165deg,#0b1f3a 0%,#07152a 100%)}
.rule{position:absolute;left:80px;right:80px;top:250px;height:1px;background:#c8a24a33}
.lens{position:absolute;right:110px;top:150px;width:340px;height:340px;border-radius:50%;
 border:3px solid #c8a24a;background:radial-gradient(circle at 35% 30%,#1d6f80,#0d3550 55%,#0b1f3a 100%);
 box-shadow:0 0 0 14px #2ba6b826, 0 0 0 16px #2ba6b866, 0 30px 90px #000a, inset 0 0 60px #2ba6b844;display:flex;align-items:center;justify-content:center}
.lens svg{width:150px;height:150px;stroke:#f0dfb4;stroke-width:1.5}
.r1{position:absolute;right:60px;top:100px;width:440px;height:440px;border-radius:50%;border:1px solid #2ba6b866}
.r2{position:absolute;right:10px;top:50px;width:540px;height:540px;border-radius:50%;border:1px solid #c8a24a1f}
.brand{position:absolute;left:80px;top:84px;font-weight:800;font-size:36px;letter-spacing:.5px;color:#f0dfb4}
.brand span{color:#c8a24a}
.chip{position:absolute;left:80px;top:160px;padding:10px 24px;border-radius:999px;border:1.5px solid #c8a24a;color:#c8a24a;font-size:22px;font-weight:600;letter-spacing:.5px}
.card{position:absolute;left:64px;right:64px;bottom:64px;padding:54px 60px 58px;border-radius:24px;background:#132c4fee;border:1px solid #c8a24a40;box-shadow:0 30px 80px #0009}
.bar{width:80px;height:6px;border-radius:3px;background:linear-gradient(90deg,#c8a24a 0 60%,#2ba6b8 60% 100%);margin-bottom:28px}
h1{font-family:PF,serif;font-weight:700;font-size:{fs}px;line-height:1.12;color:#f0dfb4}
h2{margin-top:22px;font-size:30px;line-height:1.35;font-weight:400;color:#f0dfb4b3}
</style></head><body><div class="r2"></div><div class="r1"></div>
<div class="lens">{icon}</div>
<div class="brand">Polis<span>Lupa</span></div><div class="chip">{chip}</div>
<div class="card"><div class="bar"></div><h1>{title}</h1><h2>{sub}</h2></div></body></html>"""


SLIDE = """<html><head><style>
""" + TPL.split("<style>")[1].split("*{margin:0")[0] + """
*{margin:0;box-sizing:border-box}
body{width:1080px;height:1350px;font-family:IN,sans-serif;color:#f0dfb4;overflow:hidden;padding:90px 80px;
 background:radial-gradient(circle at 85% 12%, #2ba6b833 0%, transparent 35%), linear-gradient(165deg,#0b1f3a 0%,#07152a 100%)}
.top{display:flex;justify-content:space-between;align-items:center;font-size:30px;font-weight:800}
.top span{color:#c8a24a}.num{font-size:26px;font-weight:600;color:#c8a24a;border:1.5px solid #c8a24a;border-radius:999px;padding:8px 22px}
.bar{width:90px;height:6px;border-radius:3px;background:linear-gradient(90deg,#c8a24a 0 60%,#2ba6b8 60% 100%);margin:90px 0 40px}
h1{font-family:PF,serif;font-weight:700;font-size:{fs}px;line-height:1.12}
p{margin-top:40px;font-size:38px;line-height:1.45;color:#f0dfb4d9;white-space:pre-line}
.foot{position:absolute;left:80px;right:80px;bottom:70px;font-size:26px;color:#f0dfb499;display:flex;justify-content:space-between}
</style></head><body><div class="top"><div>Polis<span>Lupa</span></div><div class="num">{num}</div></div>
<div class="bar"></div><h1>{title}</h1><p>{body}</p><div class="foot"><span>@jakhongir_bakiev</span><span>{foot}</span></div></body></html>"""


def render(items):
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1080, "height": 1080})
        for it in items:
            base = str(pathlib.Path(__file__).parent.resolve())
            if "body" in it:  # слайд карусели 1080x1350
                pg.set_viewport_size({"width": 1080, "height": 1350})
                html = SLIDE
                vals = dict(num=it.get("num", ""), title=it["title"], body=it["body"], foot=it.get("foot", "→"), fs=it.get("fs", 64))
            else:
                pg.set_viewport_size({"width": 1080, "height": 1080})
                c1, c2, c3 = THEMES[it.get("theme","auto")]
                icon = (ICONS / f"{it['icon']}.svg").read_text()
                html = TPL
                vals = dict(c1=c1, c2=c2, c3=c3, icon=icon, chip=it["chip"], title=it["title"], sub=it["sub"], fs=it.get("fs", 64))
            html = html.replace("{BASE}", base)
            for k, v in vals.items():
                html = html.replace("{" + k + "}", str(v))
            html = re.sub(r"url\('file://([^']+)'\)", lambda m: "url(data:font/" + m.group(1).rsplit('.',1)[1] + ";base64," + base64.b64encode(open(m.group(1),'rb').read()).decode() + ")", html)
            pg.set_content(html)
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(OUT / f"{it['id']}.png"))
            print("ok", it["id"])
        b.close()


if __name__ == "__main__":
    render(json.load(open(sys.argv[1], encoding="utf-8")))
