"""Simulate X profile layout: desktop banner + avatar overlap, and a phone-width crop."""
import os
from PIL import Image, ImageDraw, ImageFont
B = os.path.join(os.path.dirname(__file__), "..", "..", "site", "assets", "brand")
ban = Image.open(os.path.join(B, "x-header-1500x500.png")).convert("RGBA")
av = Image.open(os.path.join(B, "avatar-1080.png")).convert("RGBA")
f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
def avatar(d):
    a = av.resize((d, d), Image.LANCZOS); m = Image.new("L", (d, d), 0); ImageDraw.Draw(m).ellipse((0, 0, d-1, d-1), fill=255)
    return a, m
out = Image.new("RGBA", (1560, 1420), "#ffffff"); dr = ImageDraw.Draw(out)
# desktop: banner 1500 wide, avatar ~ 26% of 600px column => scaled; X desktop avatar ~ 134px on 600px banner => 335px on 1500
dx, dy = 30, 50
dr.text((dx, 12), "Desktop (banner at full size, avatar overlap simulated)", fill="#555", font=f)
out.alpha_composite(ban, (dx, dy))
d = 335; a, m = avatar(d); ring = d + 20
cx, cy = dx + 40, dy + 500 - d//2 - 10
dr.ellipse((cx, cy, cx + ring, cy + ring), fill="#ffffff"); out.paste(a, (cx + 10, cy + 10), m)
dr.text((dx + 30, cy + ring + 14), "Stationery Drop Watch", fill="#0f1419", font=fb)
dr.text((dx + 30, cy + ring + 48), "@stationerydrop", fill="#536471", font=f)
# safe-zone guide (thin dashed red) on a copy row below
# phone: 390pt wide, banner shows full width scaled, top/bottom ~60px of source cropped
py = 1020
dr.text((dx, py - 36), "Phone (390 px wide, ~60 px of banner cropped top and bottom)", fill="#555", font=f)
crop = ban.crop((0, 60, 1500, 440)); pw = 390 * 2; ph = round(crop.height * pw / 1500)
pc = crop.resize((pw, ph), Image.LANCZOS); out.alpha_composite(pc, (dx, py))
d2 = 150; a2, m2 = avatar(d2); r2 = d2 + 10
ax, ay = dx + 30, py + ph - r2 // 2
dr.ellipse((ax, ay, ax + r2, ay + r2), fill="#ffffff"); out.paste(a2, (ax + 5, ay + 5), m2)
dr.rectangle((dx, py, dx + pw, py + ph), outline="#cccccc")
# risk-zone guide beside phone: full banner downscaled with zones
gx, gy = dx + pw + 40, py
g = ban.resize((680, 227), Image.LANCZOS).convert("RGBA"); ov = Image.new("RGBA", g.size, (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
k = 680 / 1500
od.rectangle((0, 0, 679, 60*k), fill=(193, 85, 59, 50)); od.rectangle((0, 440*k, 679, 226), fill=(193, 85, 59, 50))
od.rectangle((0, 300*k, 400*k, 226), fill=(45, 42, 50, 70))
g.alpha_composite(ov); out.alpha_composite(g, (gx, gy))
dr.text((gx, gy + 240), "Risk zones: phone crop (red), avatar (grey)", fill="#555", font=f)
out.convert("RGB").save(os.path.join(B, "x-header-preview.png")); print("preview ok")
