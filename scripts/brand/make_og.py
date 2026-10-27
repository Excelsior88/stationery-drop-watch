"""Social share cards (1200x630) for Open Graph / Twitter:
site/assets/brand/og-image.png (Hobonichi side, home) and og-dotgrid.png (dot grid journaling page).
Run: python3 scripts/brand/make_og.py (needs Pillow; uses logo-1600.png)."""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
B = os.path.join(ROOT, "site", "assets", "brand")
G = "/usr/share/fonts/truetype/sand-box/google/"
INK, INK2, TERRA, CREAM, LINE, MUSTARD = "#2d2a32", "#5b5560", "#c1553b", "#fbf6ec", "#e6dccb", "#c99a2e"
W, H = 1200, 630

def card(out, lines):
    """lines: (text, font, color, gap below) drawn centred under the logo."""
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    for x in range(24, W, 28):
        for y in range(20, H, 28):
            d.ellipse((x - 1.4, y - 1.4, x + 1.4, y + 1.4), fill=LINE)
    img.paste(logo, ((W - lw) // 2, 120), logo)
    y = 120 + logo.height + 60
    for t, f, c, gap in lines:
        w = d.textlength(t, font=f)
        assert w <= W - 80, (t, w)
        d.text(((W - w) / 2, y), t, font=f, fill=c)
        y += gap
    d.rounded_rectangle((W / 2 - 60, H - 70, W / 2 + 60, H - 64), 3, fill=MUSTARD)
    img.save(os.path.join(B, out), optimize=True)
    print("wrote", out, img.size)

logo = Image.open(os.path.join(B, "logo-1600.png")).convert("RGBA")
# logo-1600.png has an opaque cream background; key it out so the dot grid runs behind the wordmark
logo.putdata([(r, g, b, 0) if (r, g, b) == (251, 246, 236) else (r, g, b, a) for r, g, b, a in logo.getdata()])
lw = 900
logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
serif = G + "Newsreader/Newsreader-VariableFont_opsz,wght.ttf"
sans = G + "Inter/Inter-VariableFont_opsz,wght.ttf"
f1 = ImageFont.truetype(serif, 52)
try: f1.set_variation_by_axes([540, 48])  # Newsreader axes: wght, opsz
except Exception: pass
f2 = ImageFont.truetype(sans, 28)
try: f2.set_variation_by_axes([28, 500])  # Inter axes: opsz, wght
except Exception: pass
f3 = ImageFont.truetype(sans, 24)
try: f3.set_variation_by_axes([24, 500])
except Exception: pass

card("og-image.png", [("Hobonichi Techo 2027 restock tracker", f1, INK, 72),
                      ("Books, Weeks & covers · checked hourly across 13 shops", f2, INK2, 0)])
card("og-dotgrid.png", [("Dot grid journal restock tracker", f1, INK, 66),
                        ("Archer and Olive · Leuchtturm1917 · Scribbles That Matter · Notebook Therapy", f3, INK2, 40),
                        ("Size by size, color by color · checked hourly", f3, TERRA, 0)])
