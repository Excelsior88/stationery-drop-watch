"""Social share cards (1200x630) for Open Graph / Twitter:
site/assets/brand/og-image.png (site-wide default: all three trackers, with Clip) and og-dotgrid.png (dot grid journals).
The default card says how many shops we check (the owner asked for "We check N shops for you", Nov 22, 2026).
N comes from build_site.N_STORES at the time you run this, so re-run it when the shop count changes;
the build prints a warning when the card's count (og-image.json) no longer matches.
The Traveler's Company and MIDORI cards were removed with those sections on Nov 19, 2026.
Clip is scripts/brand/clip-magnify.png, a trimmed copy of the approved v2 "magnify" pose.
Run: python3 scripts/brand/make_og.py (needs Pillow; uses logo-1600.png)."""
import json, os, sys
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

FREQ = "checked about every 30 minutes"

def default_card(out, shops):
    """Site-wide card: wordmark, tagline, shop count, the three trackers as chips, Clip on the right."""
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    for x in range(24, W, 28):
        for y in range(20, H, 28):
            d.ellipse((x - 1.4, y - 1.4, x + 1.4, y + 1.4), fill=LINE)
    left = 72
    wm = logo.resize((560, round(logo.height * 560 / logo.width)), Image.LANCZOS)
    img.paste(wm, (left - 6, 64), wm)
    head = ImageFont.truetype(serif, 66)
    try: head.set_variation_by_axes([560, 60])
    except Exception: pass
    sub = ImageFont.truetype(sans, 34)
    try: sub.set_variation_by_axes([32, 600])
    except Exception: pass
    chip = ImageFont.truetype(sans, 23)
    try: chip.set_variation_by_axes([24, 500])
    except Exception: pass
    y = 64 + wm.height + 44
    for t in ("Never miss a", "stationery restock"):
        d.text((left, y), t, font=head, fill=INK)
        y += 74
    y += 14
    d.text((left, y), f"We check {shops} shops for you", font=sub, fill=TERRA)
    y += 66
    x = left
    for t in ("Hobonichi Techo 2027", "Dot grid journals", "Limited-edition inks"):
        w = d.textlength(t, font=chip)
        d.rounded_rectangle((x, y, x + w + 32, y + 44), 22, fill="#ffffff", outline=LINE, width=2)
        d.text((x + 16, y + 9), t, font=chip, fill=INK)
        x += w + 32 + 12
    assert x - 12 <= 860, x
    y += 44 + 26
    d.text((left, y), FREQ[0].upper() + FREQ[1:], font=f3, fill=INK2)
    ch = 486
    c = clip.resize((round(clip.width * ch / clip.height), ch), Image.LANCZOS)
    img.paste(c, (W - c.width - 52, (H - ch) // 2 + 4), c)
    d.rounded_rectangle((left, H - 46, left + 120, H - 40), 3, fill=MUSTARD)
    img.save(os.path.join(B, out), optimize=True)
    with open(os.path.join(B, out.replace(".png", ".json")), "w") as fh:
        json.dump({"shops": shops}, fh)
        fh.write("\n")
    print("wrote", out, img.size, "shops:", shops)

clip = Image.open(os.path.join(ROOT, "scripts", "brand", "clip-magnify.png")).convert("RGBA")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_site  # noqa: E402  (module import only: reads the data files, writes nothing)
default_card("og-image.png", build_site.N_STORES)
card("og-dotgrid.png", [("Dot grid journal restock tracker", f1, INK, 66),
                        ("Archer and Olive · Leuchtturm1917 · Scribbles That Matter · Notebook Therapy", f3, INK2, 40),
                        ("Size by size, color by color · " + FREQ, f3, TERRA, 0)])
