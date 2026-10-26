"""Compose site/assets/brand/preview.png: lockup, icon, avatar in a circle crop, favicon at 32 and 16."""
import os, subprocess, io
from PIL import Image, ImageDraw, ImageFont
B = os.path.join(os.path.dirname(__file__), "..", "..", "site", "assets", "brand")
def r(svg, w):
    return Image.open(io.BytesIO(subprocess.run(["rsvg-convert", "-w", str(w), os.path.join(B, svg)], capture_output=True, check=True).stdout)).convert("RGBA")
W, H = 1600, 900
im = Image.new("RGBA", (W, H), "#f4ecdc")
d = ImageDraw.Draw(im)
f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
def card(x, y, w, h, label, fill="#fbf6ec"):
    d.rounded_rectangle((x, y, x+w, y+h), 18, fill=fill, outline="#e6dccb", width=2)
    d.text((x+16, y+h-30), label, fill="#5b5560", font=f)
card(40, 40, 1520, 260, "logo.svg (lockup)")
lg = r("logo.svg", 1200); im.alpha_composite(lg, (200, 60 + (180 - lg.height)//2))
card(40, 330, 380, 530, "icon.svg")
ic = r("icon.svg", 320); im.alpha_composite(ic, (70, 360))
card(450, 330, 520, 530, "avatar-1080.png in circular crop")
av = Image.open(os.path.join(B, "avatar-1080.png")).convert("RGBA").resize((440, 440), Image.LANCZOS)
m = Image.new("L", av.size, 0); ImageDraw.Draw(m).ellipse((0, 0, 439, 439), fill=255)
im.paste(av, (490, 360), m); d.ellipse((490, 360, 930, 800), outline="#e6dccb", width=2)
card(1000, 330, 560, 530, "favicon 32px / 16px (actual + 4x zoom)")
for i, (sz, y) in enumerate(((32, 380), (16, 600))):
    src = "favicon-32.png" if sz == 32 else None
    fv = Image.open(os.path.join(B, "favicon-32.png")).convert("RGBA") if sz == 32 else r("favicon.svg", 16)
    for bg, x in (("#ffffff", 1040), ("#2d2a32", 1110)):
        d.rectangle((x-8, y-8, x+sz+8, y+sz+8), fill=bg); im.alpha_composite(fv, (x, y))
    z = fv.resize((sz*4 if sz == 32 else sz*8,)*2, Image.NEAREST)
    d.rectangle((1200, y-8, 1200+z.width+16, y+z.height+8), fill="#ffffff"); im.alpha_composite(z, (1208, y))
    d.text((1040, y+sz+16), f"{sz}px", fill="#5b5560", font=f)
im.convert("RGB").save(os.path.join(B, "preview.png"))
print("preview ok")
