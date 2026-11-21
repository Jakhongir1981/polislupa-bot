"""Ребус в фирменном стиле: слайд-загадка и слайд-ответ (1080x1350)."""
import base64, re, pathlib, sys, json
from playwright.sync_api import sync_playwright
BASE = pathlib.Path(__file__).parent.resolve()
F = f"{BASE}/node_modules/@fontsource"
def ff(fam, w, file):
    return "".join(f"@font-face{{font-family:{fam};font-weight:{w};src:url('file://{F}/{file}-{sub}-{w}-normal.woff2'){rng}}}"
                   for sub, rng in (("latin",""),("latin-ext",";unicode-range:U+0100-024F,U+02BB-02BC,U+1E00-1EFF"),("cyrillic",";unicode-range:U+0400-04FF")))
FONTS = ff("PF",700,"playfair-display/files/playfair-display") + "".join(ff("IN",w,"inter/files/inter") for w in (400,600,800))
CSS = FONTS + """*{margin:0;box-sizing:border-box}
body{width:1080px;height:1350px;font-family:IN,sans-serif;color:#f0dfb4;overflow:hidden;padding:90px 80px;position:relative;
 background:radial-gradient(circle at 85% 12%, #2ba6b833 0%, transparent 35%), linear-gradient(165deg,#0b1f3a 0%,#07152a 100%)}
.top{display:flex;justify-content:space-between;align-items:center;font-size:30px;font-weight:800}.top span{color:#c8a24a}
.chip{font-size:26px;font-weight:600;color:#c8a24a;border:1.5px solid #c8a24a;border-radius:999px;padding:8px 22px}
.bar{width:90px;height:6px;border-radius:3px;background:linear-gradient(90deg,#c8a24a 0 60%,#2ba6b8 60% 100%);margin:70px 0 34px}
h1{font-family:PF,serif;font-weight:700;font-size:62px;line-height:1.12}
.sub{margin-top:24px;font-size:34px;color:#f0dfb4bf}
.puzzle{margin-top:80px;display:flex;align-items:center;justify-content:center;gap:28px}
.tile{width:330px;height:330px;border-radius:40px;background:#132c4f;border:2px solid #c8a24a66;display:flex;align-items:center;justify-content:center;
 font-family:'Noto Color Emoji';font-size:200px;box-shadow:0 0 0 12px #2ba6b81a, 0 30px 80px #0008;position:relative}
.plus{font-size:110px;font-weight:800;color:#2ba6b8}
.comma{position:absolute;right:-8px;top:-30px;font-family:PF,serif;font-size:190px;color:#c8a24a;line-height:1}
.hint{margin-top:90px;text-align:center;font-size:34px;color:#f0dfb4cc}
.hint b{color:#c8a24a}
.ans{margin-top:70px;font-family:PF,serif;font-size:150px;letter-spacing:12px;color:#c8a24a;text-align:center}
.eq{margin-top:40px;text-align:center;font-size:40px;color:#f0dfb4}
.eq b{color:#2ba6b8}
.txt{margin-top:56px;font-size:36px;line-height:1.45;color:#f0dfb4d9}
.foot{position:absolute;left:80px;right:80px;bottom:70px;font-size:26px;color:#f0dfb499;display:flex;justify-content:space-between}
"""
def page(inner, foot):
    return f"<html><head><style>{CSS}</style></head><body><div class='top'><div>Polis<span>Lupa</span></div><div class='chip'>Rebus kuni 🧩</div></div>{inner}<div class='foot'><span>@jakhongir_bakiev</span><span>{foot}</span></div></body></html>"
q = page("""<div class='bar'></div><h1>Rasmlardan sug'urta<br>atamasini toping</h1>
<div class='sub'>Bu so'zni sug'urtada juda ko'p eshitasiz 😉</div>
<div class='puzzle'><div class='tile'>🎲</div><div class='plus'>+</div><div class='tile'>🐝<div class='comma'>,</div></div></div>
<div class='hint'>Maslahat: <b>vergul</b> — oxirgi harfni olib tashlang</div>""", "Javob — keyingi slaydda →")
a = page("""<div class='bar'></div><h1>Javob:</h1>
<div class='ans'>ZARAR</div>
<div class='eq'>ZAR 🎲 + AR<s>I</s> 🐝 = <b>ZARAR</b></div>
<div class='txt'>Zarar — sug'urta hodisasida ko'rilgan moddiy yo'qotish. Aynan uni sug'urta kompaniyasi to'lab beradi: avtomobil ta'miri, kvartira yoki biznes mulki.<br><br>Zararingiz to'liq qoplanishi uchun polis shartlarini oldindan tekshiring.</div>""", "Polisni tekshirish — bot orqali")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width":1080,"height":1350})
    out = BASE / "out"; out.mkdir(exist_ok=True)
    for name, html in (("rebus-zarar-1", q), ("rebus-zarar-2", a)):
        html = re.sub(r"url\('file://([^']+)'\)", lambda m: "url(data:font/woff2;base64," + base64.b64encode(open(m.group(1),'rb').read()).decode() + ")", html)
        pg.set_content(html); pg.wait_for_timeout(500); pg.screenshot(path=str(out / f"{name}.png")); print("ok", name)
    b.close()
