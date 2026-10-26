"""Social share card (1200x630) for Open Graph / Twitter: site/assets/brand/og-image.png.
Run: python3 scripts/brand/make_og.py (needs Pillow; uses logo-1600.png)."""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
B = os.path.join(ROOT, "site", "assets", "brand")
G = "/usr/share/fonts/truetype/sand-box/google/"
INK, INK2, TERRA, CREAM, LINE, MUSTARD = "#2d2a32", "#5b5560", "#c1553b", "#fbf6ec", "#e6dccb", "#c99a2e"
W, H = 1200, 630

img = Image.new("RGB", (W, H), CREAM)
d = ImageDraw.Draw(img)
for x in range(24, W, 28):
    for y in range(20, H, 28):
        d.ellipse((x - 1.4, y - 1.4, x + 1.4, y + 1.4), fill=LINE)
logo = Image.open(os.path.join(B, "logo-1600.png")).convert("RGBA")
# logo-1600.png has an opaque cream background; key it out so the dot grid runs behind the wordmark
logo.putdata([(r, g, b, 0) if (r, g, b) == (251, 246, 236) else (r, g, b, a) for r, g, b, a in logo.getdata()])
lw = 900
logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
img.paste(logo, ((W - lw) // 2, 120), logo)
serif = G + "Newsreader/Newsreader-VariableFont_opsz,wght.ttf"
sans = G + "Inter/Inter-VariableFont_opsz,wght.ttf"
f1 = ImageFont.truetype(serif, 52)
try: f1.set_variation_by_axes([540, 48])  # Newsreader axes: wght, opsz
except Exception: pass
f2 = ImageFont.truetype(sans, 28)
try: f2.set_variation_by_axes([28, 500])  # Inter axes: opsz, wght
except Exception: pass
t1 = "Hobonichi Techo 2027 restock tracker"
t2 = "Books, Weeks & covers · checked hourly across 13 shops"
y = 120 + logo.height + 60
for t, f, c, gap in ((t1, f1, INK, 72), (t2, f2, INK2, 0)):
    w = d.textlength(t, font=f)
    d.text(((W - w) / 2, y), t, font=f, fill=c)
    y += gap
d.rounded_rectangle((W / 2 - 60, H - 70, W / 2 + 60, H - 64), 3, fill=MUSTARD)
img.save(os.path.join(B, "og-image.png"), optimize=True)
print("wrote og-image.png", img.size)
