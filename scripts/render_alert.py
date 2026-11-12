#!/usr/bin/env python3
"""Render a Stationery Drop Watch drop-alert card (1080x1080 PNG) plus its captions.

Usage:
  python3 scripts/render_alert.py --kind restock|new --store "Wonder Pens" \
      --product "Hobonichi Weeks Mega 2027 (English)" [--variant "Bow & Tie: Candy Dream"] \
      --store-url https://... --page-url https://stationerydropwatch.com/<page>/ \
      --at 2026-10-28T19:20:37+00:00 [--from-status coming_soon] [--note "Candy Dream"] \
      [--out-dir alerts/out] [--slug name]

Writes <out-dir>/<slug>.png, <slug>.json and <slug>.md. Never overwrites: if a name is taken it
uses <slug>-2, <slug>-3, ... The detected time is converted to America/Detroit.
"""
import argparse, datetime as dt, json, os, re, sys
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alert_captions as cap  # noqa: E402
import clip_mascot  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = os.path.join(ROOT, "site/assets/brand/logo-1600.png")
FONT_DIR = os.environ.get("ALERT_FONT_DIR", "/usr/share/fonts/truetype/sand-box/google")
NR = f"{FONT_DIR}/Newsreader/Newsreader-VariableFont_opsz,wght.ttf"
NRI = f"{FONT_DIR}/Newsreader/Newsreader-Italic-VariableFont_opsz,wght.ttf"
IN = f"{FONT_DIR}/Inter/Inter-VariableFont_opsz,wght.ttf"
TZ = ZoneInfo("America/Detroit")
S = 1080

hx = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
# Colors from site/assets/style.css
PAPER, CARD, INK, INK2, LINE = hx("#fbf6ec"), hx("#fffdf8"), hx("#2d2a32"), hx("#5b5560"), hx("#e6dccb")
RUST, SAGE, MUST = hx("#c1553b"), hx("#5f8a6b"), hx("#c99a2e")
STATUS_WORDS = {"sold_out": "sold out", "coming_soon": "coming soon", "preorder": "preorder", "out_of_stock": "out of stock",
                "unavailable": "unavailable", "unknown": None, "": None}

_fc = {}
def F(path, size, w, opsz=None):
    key = (path, round(size, 1), w, opsz)
    if key in _fc:
        return _fc[key]
    f = ImageFont.truetype(path, max(1, round(size)))
    vals = []
    for a in f.get_variation_axes():
        n = a["name"].lower()
        vals.append(w if b"weight" in n else min(max(opsz or size, a["minimum"]), a["maximum"]))
    f.set_variation_by_axes(vals)
    _fc[key] = f
    return f


def wrap(d, text, font, width, max_lines):
    """Greedy word wrap. Returns list of lines or None if it doesn't fit in max_lines."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=font) <= width:
            cur = t
        else:
            if not cur or d.textlength(w, font=font) > width:
                return None
            lines.append(cur); cur = w
    lines.append(cur)
    return lines if len(lines) <= max_lines else None


def fit_lines(d, text, mk_font, sizes, width, max_lines):
    for s in sizes:
        f = mk_font(s)
        for n in range(1, max_lines + 1):
            ls = wrap(d, text, f, width, n)
            if ls:
                return f, s, ls
    raise ValueError(f"text does not fit: {text!r}")


def shadow(base, box, r, off=(0, 14), blur=22, a=70):
    L = Image.new("RGBA", base.size, (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.rounded_rectangle((box[0] + off[0], box[1] + off[1], box[2] + off[0], box[3] + off[1]), r, fill=(70, 45, 25, a))
    base.alpha_composite(L.filter(ImageFilter.GaussianBlur(blur)))


def bg():
    im = Image.new("RGBA", (S, S), hx("#dfe6d6") + (255,))
    rng = np.random.default_rng(3); n = rng.normal(0, 5, (S, S))
    n = Image.fromarray(np.clip(128 + n, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    im.alpha_composite(Image.merge("RGBA", [n, n, n, Image.new("L", (S, S), 18)]))
    yy, xx = np.mgrid[0:S, 0:S] / S; g = np.clip(1 - np.hypot(xx - .5, yy - .45) / 0.75, 0, 1) * 60
    im.alpha_composite(Image.merge("RGBA", [Image.new("L", (S, S), c) for c in (255, 250, 235)] + [Image.fromarray(g.astype(np.uint8))]))
    return im


def text_sp(d, xy, s, f, fill, sp, anchor="ls"):
    x, y = xy
    if anchor[0] == "m":
        tw = sum(d.textlength(c, font=f) for c in s) + sp * (len(s) - 1); x -= tw / 2; anchor = "l" + anchor[1]
    for c in s:
        d.text((x, y), c, font=f, fill=fill, anchor=anchor); x += d.textlength(c, font=f) + sp


def bow(d, cx, cy, s, col):
    d.polygon([(cx, cy), (cx - s * 1.4, cy - s * 0.8), (cx - s * 1.5, cy + s * 0.8)], fill=col)
    d.polygon([(cx, cy), (cx + s * 1.4, cy - s * 0.8), (cx + s * 1.5, cy + s * 0.8)], fill=col)
    d.polygon([(cx - 4, cy), (cx - s * 0.7, cy + s * 1.8), (cx - s * 0.25, cy + s * 1.6)], fill=col)
    d.polygon([(cx + 4, cy), (cx + s * 0.7, cy + s * 1.8), (cx + s * 0.25, cy + s * 1.6)], fill=col)
    d.ellipse((cx - s * 0.32, cy - s * 0.32, cx + s * 0.32, cy + s * 0.32), fill=tuple(int(c * 0.8) for c in col))


def bell(d, cx, cy, s, col):
    """Alert-bell doodle (brand icon motif) for products without a bow."""
    dark = tuple(int(c * 0.8) for c in col)
    d.ellipse((cx - s * 0.18, cy - s * 1.25, cx + s * 0.18, cy - s * 0.9), fill=dark)
    d.chord((cx - s * 0.9, cy - s * 1.05, cx + s * 0.9, cy + s * 0.9), 180, 360, fill=col)
    d.polygon([(cx - s * 0.9, cy - s * 0.1), (cx + s * 0.9, cy - s * 0.1), (cx + s * 1.15, cy + s * 0.75), (cx - s * 1.15, cy + s * 0.75)], fill=col)
    d.rounded_rectangle((cx - s * 1.3, cy + s * 0.65, cx + s * 1.3, cy + s * 0.9), 4, fill=dark)
    d.ellipse((cx - s * 0.28, cy + s * 0.85, cx + s * 0.28, cy + s * 1.35), fill=dark)
    for sgn in (-1, 1):  # little "ringing" marks
        d.line((cx + sgn * s * 1.35, cy - s * 0.55, cx + sgn * s * 1.75, cy - s * 0.8), fill=col, width=3)
        d.line((cx + sgn * s * 1.45, cy - s * 0.05, cx + sgn * s * 1.9, cy - s * 0.1), fill=col, width=3)


def tape(text, w=380, h=66, col=MUST, angle=-8):
    T = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(T)
    rng = np.random.default_rng(7)
    pts = [(0, 0), (w, 0)] + [(w - 6 + rng.integers(-5, 6), y) for y in range(0, h + 1, 8)] + [(w, h), (0, h)] + \
          [(6 + rng.integers(-5, 6), y) for y in range(h, -1, -8)]
    d.polygon(pts, fill=col + (235,))
    for x in range(14, w - 10, 26):
        d.ellipse((x, 8, x + 7, 15), fill=(255, 250, 235, 120)); d.ellipse((x + 13, h - 15, x + 20, h - 8), fill=(255, 250, 235, 120))
    if text:
        d.text((w / 2, h / 2 + 1), text, font=F(IN, 24, 800), fill=INK, anchor="mm")
    return T.rotate(angle, expand=True, resample=Image.BICUBIC)


def month_label(days):
    m0, m1 = days[0].strftime("%b").upper(), days[-1].strftime("%b").upper()
    return f"{m0} / {m1}" if m0 != m1 else days[0].strftime("%B").upper()


def planner(local, note, kind, from_label, doodle, w=720, h=414):
    P = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(P)
    ox, oy = 20, 20
    d.rounded_rectangle((ox - 12, oy - 10, ox + w + 12, oy + h + 12), 18, fill=hx("#b9839a"))
    d.rounded_rectangle((ox, oy, ox + w, oy + h), 8, fill=CARD)
    mid = ox + w // 2
    for i in range(26):
        a = int(60 * (1 - i / 26) ** 2)
        d.line((mid - i, oy, mid - i, oy + h), fill=(120, 95, 70, a)); d.line((mid + i, oy, mid + i, oy + h), fill=(120, 95, 70, a))
    # left page: the real Mon-Sun week of the drop
    lx0, lx1 = ox + 34, mid - 34
    monday = local.date() - dt.timedelta(days=local.weekday())
    days = [monday + dt.timedelta(days=i) for i in range(7)]
    d.text((lx0, oy + 28), month_label(days), font=F(IN, 15, 700), fill=RUST, anchor="ls")
    top = oy + 44; rh = (h - 60) / 7
    fd = F(IN, 13, 700); fn = F(NR, 28, 600, opsz=28)
    for i, day in enumerate(days):
        y = top + i * rh
        d.line((lx0, y, lx1, y), fill=LINE, width=2)
        col = RUST if day.weekday() >= 5 else INK
        d.text((lx0 + 2, y + rh * 0.52), str(day.day), font=fn, fill=col, anchor="lm")
        d.text((lx0 + 48, y + rh * 0.52), day.strftime("%a").upper(), font=fd, fill=INK2, anchor="lm")
    d.line((lx0, top + 7 * rh, lx1, top + 7 * rh), fill=LINE, width=2)
    # sticky note (highlighter swipe) on the drop day
    di = local.weekday(); y0, y1 = top + di * rh, top + (di + 1) * rh
    HL = Image.new("RGBA", P.size, (0, 0, 0, 0)); hd = ImageDraw.Draw(HL)
    nb = (lx0 + 88, y0 + 9, lx1 + 4, y1 - 7)
    hd.rounded_rectangle(nb, 10, fill=MUST + (95,))
    P.alpha_composite(HL); d = ImageDraw.Draw(P)
    suffix = ": back!" if kind == "restock" else ": orderable!"
    nw = nb[2] - nb[0] - 20; nh = nb[3] - nb[1] - 4
    placed = False
    for lines_max, sizes in ((1, range(18, 12, -1)), (2, range(15, 10, -1))):
        for s in sizes:
            f = F(NRI, s, 600, opsz=s)
            ls = wrap(d, note + suffix, f, nw, lines_max)
            if ls and len(ls) * s * 1.05 <= nh:
                lh = s * 1.05; cy = (y0 + y1) / 2 + 1 - lh * (len(ls) - 1) / 2
                for k, ln in enumerate(ls):
                    d.text((nb[0] + 10, cy + k * lh), ln, font=f, fill=INK, anchor="lm")
                placed = True; break
        if placed:
            break
    if not placed:  # very long name: shorten with an ellipsis rather than overflow
        f = F(NRI, 12, 600, opsz=12); t = note
        while t and d.textlength(t + "…" + suffix, font=f) > nw:
            t = t[:-1]
        d.text((nb[0] + 10, (y0 + y1) / 2 + 1), t.rstrip() + "…" + suffix, font=f, fill=INK, anchor="lm")
    d.ellipse((lx0 - 10 + (6 if local.day < 10 else 0), y0 + 4, lx0 + 44 - (14 if local.day < 10 else 0), y1 - 2), outline=RUST, width=3)
    # right page: grid, doodle, time
    rx0, rx1 = mid + 30, ox + w - 30
    for x in range(rx0, rx1 + 1, 22): d.line((x, oy + 30, x, oy + h - 24), fill=LINE + (255,), width=1)
    for y in range(oy + 30, oy + h - 23, 22): d.line((rx0, y, rx1, y), fill=LINE + (255,), width=1)
    cx = (rx0 + rx1) / 2
    (bow if doodle == "bow" else bell)(d, cx, oy + 118, 30 if doodle == "bow" else 34, RUST)
    d.text((cx, oy + 222), local.strftime("%-I:%M %p"), font=F(NR, 40, 600, opsz=40), fill=INK, anchor="ms")
    d.text((cx, oy + 256), f"{local.tzname()}  ·  {local.strftime('%A, %b %-d').upper()}", font=F(IN, 14, 700), fill=INK2, anchor="ms")
    to = "back in stock" if kind == "restock" else "orderable"
    if from_label:
        l1, l2 = "went from", f"\u201c{from_label}\u201d to"
    else:
        l1, l2 = ("came back", "and is now") if kind == "restock" else ("just listed", "and now")
    d.text((cx, oy + 308), l1, font=F(NRI, 22, 500, opsz=22), fill=INK2, anchor="ms")
    d.text((cx, oy + 338), l2, font=F(NRI, 22, 500, opsz=22), fill=INK2, anchor="ms")
    d.text((cx, oy + 372), to, font=F(NR, 30, 700, opsz=30), fill=SAGE, anchor="ms")
    d.polygon([(mid + 70, oy + h - 6), (mid + 88, oy + h - 6), (mid + 88, oy + h + 38), (mid + 79, oy + h + 28), (mid + 70, oy + h + 38)], fill=RUST)
    return P


def headline_layout(d, head, store, product, variant):
    """Find the largest scale at which headline, store, product and variant fit between y=180 and y=500."""
    W, TOP, BOT = 968, 193, 500  # r5: first baseline 268 at full size
    WV = 780  # product/variant lines sit beside the left washi tape (x<~180, y>~430): keep them narrower
    for s in [x / 100 for x in range(100, 39, -3)]:
        hs = 104 * s
        fH, fHi = F(NR, hs, 600, opsz=72), F(NRI, hs, 600, opsz=72)
        if d.textlength(head, font=fH) > W:
            continue
        st = wrap(d, f"at {store}.", fHi, W, 2)
        if not st:
            continue
        ps = max(24, 34 * min(1, s * 1.15)); vs = max(26, 40 * min(1, s * 1.15))
        try:
            fP, ps, pl = fit_lines(d, product, lambda z: F(IN, z, 700, opsz=32), [z for z in range(round(ps), 19, -1)], WV, 2)
            if variant:
                fV, vs, vl = fit_lines(d, variant, lambda z: F(NRI, z, 600, opsz=40), [z for z in range(round(vs), 21, -1)], WV, 2)
            else:
                fV, vl = None, []
        except ValueError:
            continue
        rows = [(head, fH, INK, hs)] + [(t, fHi, RUST, hs) for t in st]
        base = [TOP + 0.72 * hs]
        for _ in st:
            base.append(base[-1] + 1.0 * hs)
        prev = hs; seq = []
        for i, t in enumerate(pl):
            base.append(base[-1] + (0.33 * prev + 0.85 * ps if i == 0 else 1.25 * ps)); seq.append((t, fP, INK, ps))
        prev_p = ps
        for i, t in enumerate(vl):
            base.append(base[-1] + (0.45 * prev_p + 0.85 * vs if i == 0 else 1.15 * vs)); seq.append((t, fV, SAGE, vs))
        rows += seq
        last_size = rows[-1][3]
        if base[-1] + 0.28 * last_size <= BOT:
            # centre the block vertically in the slot, but never higher than the approved r5 position
            slack = BOT - (base[-1] + 0.28 * last_size)
            shift = slack / 2 if len(rows) > 4 else 0  # wrapped (long) names: centre in the slot
            return [(t, f, c, b + shift) for (t, f, c, _), b in zip(rows, base)]
    raise ValueError("headline block does not fit")


def build(store, product, variant, local, kind, from_label, note, doodle):
    im = bg(); d = ImageDraw.Draw(im)
    logo = Image.open(LOGO).convert("RGBA")
    lw = 430; logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
    lb = (56, 48, 56 + lw + 28, 48 + logo.height + 20)
    shadow(im, lb, 14, off=(0, 6), blur=10, a=50)
    d.rounded_rectangle(lb, 14, fill=PAPER); im.alpha_composite(logo, (lb[0] + 14, lb[1] + 10))
    fp = F(IN, 22, 800); t = "DROP ALERT"
    pw = d.textlength(t, font=fp) + 3 * 9 + 56
    pb = (S - 56 - pw, lb[1] + 14, S - 56, lb[3] - 14)
    d.rounded_rectangle(pb, 999, fill=RUST)
    text_sp(d, ((pb[0] + pb[2]) / 2, (pb[1] + pb[3]) / 2 + 8), t, fp, PAPER, 3, anchor="ms")
    head = "Back in stock" if kind == "restock" else "Now available"
    for txt, f, c, b in headline_layout(d, head, store, product, variant):
        d.text((S / 2, b), txt, font=f, fill=c, anchor="ms")
    P = planner(local, note, kind, from_label, doodle)
    Pr = P.rotate(2, expand=True, resample=Image.BICUBIC)
    px = (S - Pr.width) // 2; py = 516
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); m = Pr.split()[3].point(lambda a: min(a, 90))
    blk = Image.new("RGBA", Pr.size, (70, 45, 25, 255)); blk.putalpha(m); sh.alpha_composite(blk, (px + 6, py + 18))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16))); im.alpha_composite(Pr, (px, py))
    T = tape("BACK IN STOCK" if kind == "restock" else "NOW ORDERABLE", angle=-9)
    im.alpha_composite(T, (px + Pr.width - T.width + 70, py - 14))
    im.alpha_composite(tape("", w=130, h=46, col=SAGE, angle=-38), (px - 100, py - 58))
    d = ImageDraw.Draw(im)
    d.rectangle((0, S - 70, S, S), fill=INK)
    d.text((S / 2, S - 26), "stationerydropwatch.com", font=F(IN, 26, 700), fill=PAPER, anchor="ms")
    # Clip: cheer pose for back-in-stock and now-available singles. Kept small in
    # the lower-left margin, above the footer, so names, the planner and the URL stay clear.
    clip_mascot.place_for_kind(im, kind, layout="alert")
    return im.convert("RGB")


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:70].strip("-")


def free_stem(out_dir, slug):
    for i in range(1, 1000):
        stem = os.path.join(out_dir, slug if i == 1 else f"{slug}-{i}")
        if not any(os.path.exists(stem + e) for e in (".png", ".json", ".md")):
            return stem
    raise SystemExit("no free output name")


def write_new(path, data, mode="xb"):
    with open(path, mode) as f:  # 'x' = fail rather than overwrite
        f.write(data)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", required=True, choices=["restock", "new"], help="restock = was sold out and is back; new = first time orderable")
    ap.add_argument("--product", required=True); ap.add_argument("--variant", default="")
    ap.add_argument("--store", required=True)
    ap.add_argument("--store-url", required=True, help="the store's product page")
    ap.add_argument("--page-url", required=True, help="our stationerydropwatch.com page for this product")
    ap.add_argument("--at", required=True, help="detected time, ISO 8601 with zone (changes.json 'at')")
    ap.add_argument("--from-status", default=None, help="previous status from changes.json, e.g. sold_out / coming_soon")
    ap.add_argument("--note", default=None, help="short name for the sticky note (default: last ':' part of variant, else product)")
    ap.add_argument("--doodle", choices=["auto", "bow", "bell"], default="auto")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "alerts", "out"))
    ap.add_argument("--slug", default=None)
    a = ap.parse_args(argv)

    for u, name in ((a.store_url, "--store-url"), (a.page_url, "--page-url")):
        if not re.match(r"https://", u):
            ap.error(f"{name} must be an https URL")
    if not re.match(r"https://(www\.)?stationerydropwatch\.com/", a.page_url):
        ap.error("--page-url must be on stationerydropwatch.com")
    when = dt.datetime.fromisoformat(a.at.replace("Z", "+00:00"))
    if when.tzinfo is None:
        ap.error("--at needs a time zone (e.g. +00:00)")
    local = when.astimezone(TZ)
    fs = (a.from_status or "").strip().lower().replace(" ", "_")
    from_label = STATUS_WORDS.get(fs, fs.replace("_", " ") or None)
    if a.kind == "new" and from_label in ("sold out", "out of stock"):
        ap.error("kind 'new' with from-status sold_out looks like a restock; check the change")
    note = a.note or (a.variant or a.product).split(":")[-1].strip()
    doodle = a.doodle if a.doodle != "auto" else ("bow" if "bow" in f"{a.product} {a.variant}".lower() else "bell")
    for field, val in (("store", a.store), ("product", a.product), ("variant", a.variant), ("note", note)):
        cap.check_text(val, a.kind, where=field)

    captions = cap.build(a.product, a.variant, a.store, a.page_url, local, a.kind, from_label)
    im = build(a.store, a.product, a.variant, local, a.kind, from_label, note, doodle)

    os.makedirs(a.out_dir, exist_ok=True)
    stem = free_stem(a.out_dir, a.slug or slugify(f"{a.store} {a.variant or a.product} {local:%Y%m%d-%H%M}"))
    import io
    buf = io.BytesIO(); im.save(buf, "PNG")
    meta = dict(kind=a.kind, store=a.store, product=a.product, variant=a.variant, store_url=a.store_url, page_url=a.page_url,
                detected_at=a.at, detected_local=local.isoformat(), local_label=f"{local:%A, %B %-d, %Y, %-I:%M %p} {local.tzname()}",
                from_status=a.from_status, image=os.path.abspath(stem + ".png"), captions=captions)
    md = (f"# Drop alert: {a.product}{' · ' + a.variant if a.variant else ''} at {a.store}\n\n"
          f"Kind: {a.kind} · Detected: {meta['local_label']} · Store page: {a.store_url}\n\n"
          f"## X ({captions['x_weighted_len']}/280, link counted as 23)\n\n{captions['x']}\n\n"
          f"## Instagram\n\n{captions['instagram']}\n\n## Threads (topic: {captions['threads_topic']})\n\n{captions['threads']}\n\n"
          f"## Bluesky ({captions['bluesky_len']}/300)\n\n{captions['bluesky']}\n")
    write_new(stem + ".png", buf.getvalue())
    write_new(stem + ".json", json.dumps(meta, indent=1, ensure_ascii=False).encode())
    write_new(stem + ".md", md.encode())
    stem = os.path.abspath(stem)
    print(json.dumps({"png": stem + ".png", "json": stem + ".json", "md": stem + ".md"}))


if __name__ == "__main__":
    try:
        main()
    except cap.AlertTextError as e:
        sys.exit(f"refused: {e}")
