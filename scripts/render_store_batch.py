#!/usr/bin/env python3
"""Render ONE Stationery Drop Watch store batch card (1080x1080 PNG) listing several items from one store.

Owner rule 2026-11-10: 3+ verified items from one store at once go out as one social post per account.
Same visual style as render_alert.py (paper background, logo, DROP ALERT pill, washi tape, planner card,
dark footer). Each row shows the product, the variant, the detected time with its zone, and the lane
("back in stock" or "now available"); mixed lanes are allowed.

Usage (normally run by `alertq.py render-batch`, which builds the spec from the queued facts):
  python3 scripts/render_store_batch.py --spec spec.json [--out-dir alerts/out] [--slug name]

spec.json: {"store": ..., "store_id": ..., "tracker_url": ..., "items": [{"product", "variant", "lane",
            "detected_at", "from", "store_url", "page_url"}, ...]}
Writes <slug>.png, <slug>.json and <slug>.md; never overwrites.
"""
import argparse, datetime as dt, io, json, os, re, sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alert_captions as cap  # noqa: E402
import clip_mascot  # noqa: E402
import render_alert as ra  # noqa: E402
from render_alert import F, IN, NR, NRI, INK, INK2, LINE, RUST, SAGE, MUST, CARD, PAPER, S, TZ, hx  # noqa: E402

LANE_WORD = {"restock": "back in stock", "new_availability": "now available"}
LANE_KIND = {"restock": "restock", "new_availability": "new"}
MIN_BATCH = 3


def fit_one(d, text, path, sizes, w, width, opsz_same=True):
    for s in sizes:
        f = F(path, s, w, opsz=s if opsz_same else None)
        if d.textlength(text, font=f) <= width:
            return f, text
    f = F(path, sizes[-1], w, opsz=sizes[-1])
    t = text
    while t and d.textlength(t + "…", font=f) > width:
        t = t[:-1]
    return f, t.rstrip(" ,:;·-(") + "…"


def headline(lanes):
    if lanes == {"restock"}:
        return "Just restocked", "JUST RESTOCKED"
    if lanes == {"new_availability"}:
        return "Now available", "NOW AVAILABLE"
    return "Just dropped", "JUST DROPPED"


def card(items, store, lanes, w=900, h=None):
    """A planner-style sheet: header with the day and zone, then one ruled row per item."""
    n_rows = min(len(items), 8)
    if h is None:
        h = int(min(560, 66 + n_rows * 104 + 22))
    P = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(P)
    ox, oy = 20, 20
    d.rounded_rectangle((ox - 12, oy - 10, ox + w + 12, oy + h + 12), 18, fill=hx("#b9839a"))
    d.rounded_rectangle((ox, oy, ox + w, oy + h), 8, fill=CARD)
    x0, x1 = ox + 40, ox + w - 40
    locs = [it["local"] for it in items]
    days = sorted({l.date() for l in locs})
    zones = sorted({l.tzname() for l in locs})
    if len(days) == 1:
        day_label = locs[0].strftime("%A, %B %-d").upper()
    else:
        day_label = f"{min(locs).strftime('%a %b %-d').upper()} TO {max(locs).strftime('%a %b %-d').upper()}"
    d.text((x0, oy + 46), day_label, font=F(IN, 17, 700), fill=RUST, anchor="ls")
    d.text((x0 + d.textlength(day_label, font=F(IN, 17, 700)) + 10, oy + 46), f"·  {len(items)} ITEMS  ·  TIMES {'/'.join(zones)}",
           font=F(IN, 15, 700), fill=INK2, anchor="ls")
    top = oy + 66
    d.line((x0, top, x1, top), fill=LINE, width=2)
    show = items
    more = 0
    max_rows = 8
    if len(items) > max_rows:
        show, more = items[: max_rows - 1], len(items) - (max_rows - 1)
    rows = len(show) + (1 if more else 0)
    rh = min(104, (oy + h - 22 - top) / rows)
    two_line = rh >= 74
    multi_day = len(days) > 1
    right_w = 200
    name_w = x1 - x0 - right_w - 30
    for i, it in enumerate(show):
        y = top + i * rh
        cy = y + rh / 2
        if two_line:
            fP, tP = fit_one(d, it["product"], IN, list(range(22, 15, -1)), 700, name_w)
            d.text((x0, cy - 6), tP, font=fP, fill=INK, anchor="ls")
            if it["variant"]:
                fV, tV = fit_one(d, it["variant"], NRI, list(range(30, 19, -1)), 600, name_w)
                d.text((x0, cy + 26), tV, font=fV, fill=SAGE, anchor="ls")
        else:
            label = f"{it['product']} · {it['variant']}" if it["variant"] else it["product"]
            fP, tP = fit_one(d, label, IN, list(range(21, 14, -1)), 700, name_w)
            d.text((x0, cy + 7), tP, font=fP, fill=INK, anchor="ls")
        t = it["local"].strftime("%a %-I:%M %p" if multi_day else "%-I:%M %p") + " " + it["local"].tzname()
        lane = LANE_WORD[it["lane"]]
        if two_line:
            d.text((x1, cy - 6), t, font=F(NR, 26, 600, opsz=26), fill=INK, anchor="rs")
            d.text((x1, cy + 24), lane, font=F(NRI, 22, 600, opsz=22), fill=SAGE if it["lane"] == "restock" else RUST, anchor="rs")
        else:
            d.text((x1, cy + 7), f"{t}  ·  {lane}", font=F(IN, 16, 700), fill=SAGE if it["lane"] == "restock" else RUST, anchor="rs")
        d.line((x0, y + rh, x1, y + rh), fill=LINE, width=2)
    if more:
        y = top + len(show) * rh
        d.text(((x0 + x1) / 2, y + rh / 2 + 8), f"+ {more} more on stationerydropwatch.com", font=F(NRI, 22, 600, opsz=22), fill=INK2, anchor="ms")
    d.polygon([(ox + 70, oy + h - 6), (ox + 88, oy + h - 6), (ox + 88, oy + h + 38), (ox + 79, oy + h + 28), (ox + 70, oy + h + 38)], fill=RUST)
    return P


def build(store, items):
    lanes = {it["lane"] for it in items}
    head, tape_text = headline(lanes)
    im = ra.bg(); d = ImageDraw.Draw(im)
    logo = Image.open(ra.LOGO).convert("RGBA")
    lw = 430; logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
    lb = (56, 48, 56 + lw + 28, 48 + logo.height + 20)
    ra.shadow(im, lb, 14, off=(0, 6), blur=10, a=50)
    d.rounded_rectangle(lb, 14, fill=PAPER); im.alpha_composite(logo, (lb[0] + 14, lb[1] + 10))
    fp = F(IN, 22, 800); t = "DROP ALERT"
    pw = d.textlength(t, font=fp) + 3 * 9 + 56
    pb = (S - 56 - pw, lb[1] + 14, S - 56, lb[3] - 14)
    d.rounded_rectangle(pb, 999, fill=RUST)
    ra.text_sp(d, ((pb[0] + pb[2]) / 2, (pb[1] + pb[3]) / 2 + 8), t, fp, PAPER, 3, anchor="ms")
    # headline: "Just restocked" / "at <Store>."
    W = 968
    for s in [x / 100 for x in range(100, 39, -3)]:
        hs = 92 * s
        fH, fHi = F(NR, hs, 600, opsz=72), F(NRI, hs, 600, opsz=72)
        if d.textlength(head, font=fH) <= W and d.textlength(f"at {store}.", font=fHi) <= W:
            break
    y1 = 190 + 0.72 * hs
    d.text((S / 2, y1), head, font=fH, fill=INK, anchor="ms")
    d.text((S / 2, y1 + hs * 0.98), f"at {store}.", font=fHi, fill=RUST, anchor="ms")
    P = card(items, store, lanes)
    Pr = P.rotate(1.2, expand=True, resample=Image.BICUBIC)
    px = (S - Pr.width) // 2; py = 392 + max(0, (952 - 392 - Pr.height) // 2)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); m = Pr.split()[3].point(lambda a: min(a, 90))
    blk = Image.new("RGBA", Pr.size, (70, 45, 25, 255)); blk.putalpha(m); sh.alpha_composite(blk, (px + 6, py + 18))
    im.alpha_composite(sh.filter(ra.ImageFilter.GaussianBlur(16))); im.alpha_composite(Pr, (px, py))
    T = ra.tape(tape_text, angle=-7)
    im.alpha_composite(T, (px + Pr.width - T.width + 40, py - 40))
    im.alpha_composite(ra.tape("", w=130, h=46, col=SAGE, angle=-38), (px - 60, py - 40))
    d = ImageDraw.Draw(im)
    d.rectangle((0, S - 70, S, S), fill=INK)
    d.text((S / 2, S - 26), "stationerydropwatch.com", font=F(IN, 26, 700), fill=PAPER, anchor="ms")
    # Clip: cheer pose (batches are restocks / now-available). Stands in the
    # lower-left corner, feet on the footer (left of the URL), so the larger
    # size does not cover names, times or lane words.
    clip_mascot.place_for_kind(im, "store_batch", layout="batch")
    return im.convert("RGB")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out-dir", default=os.path.join(ra.ROOT, "alerts", "out"))
    ap.add_argument("--slug", default=None)
    a = ap.parse_args(argv)
    spec = json.loads(open(a.spec).read())
    store, raw = spec["store"], spec["items"]
    if len(raw) < MIN_BATCH:
        raise cap.AlertTextError(f"a store batch needs {MIN_BATCH}+ items, got {len(raw)}")
    tracker = spec.get("tracker_url") or ""
    if not re.match(r"https://(www\.)?stationerydropwatch\.com/", tracker):
        ap.error("tracker_url must be on stationerydropwatch.com")
    cap.check_text(store, "restock", where="store")
    items = []
    for it in raw:
        if it["lane"] not in LANE_WORD:
            ap.error(f"unknown lane {it['lane']}")
        when = dt.datetime.fromisoformat(it["detected_at"].replace("Z", "+00:00"))
        if when.tzinfo is None:
            ap.error("detected_at needs a time zone")
        for field in ("product", "variant"):
            cap.check_text(it.get(field) or "", LANE_KIND[it["lane"]], where=field)
        if it["lane"] == "new_availability" and (it.get("from") or "") in ("sold_out", "out_of_stock"):
            ap.error("now-available item with from sold_out looks like a restock; check the change")
        items.append({**it, "variant": it.get("variant") or "", "local": when.astimezone(TZ)})
    items.sort(key=lambda it: it["local"])
    im = build(store, items)
    os.makedirs(a.out_dir, exist_ok=True)
    stem = ra.free_stem(a.out_dir, a.slug or ra.slugify(f"storebatch {store} {items[0]['local']:%Y%m%d-%H%M}"))
    buf = io.BytesIO(); im.save(buf, "PNG")
    meta = dict(kind="store_batch", store=store, store_id=spec.get("store_id"), tracker_url=tracker,
                items=[{k: v for k, v in it.items() if k != "local"} | {"detected_local": it["local"].isoformat(),
                        "local_label": f"{it['local']:%A, %B %-d, %Y, %-I:%M %p} {it['local'].tzname()}",
                        "lane_word": LANE_WORD[it["lane"]]} for it in items],
                image=os.path.abspath(stem + ".png"))
    md = f"# Store batch: {len(items)} items at {store}\n\nTracker: {tracker}\n\n" + "\n".join(
        f"- {it['product']}{' · ' + it['variant'] if it['variant'] else ''}: {LANE_WORD[it['lane']]}, "
        f"{it['local']:%a %b %-d %-I:%M %p} {it['local'].tzname()}" for it in items) + \
        "\n\nCaptions come from `alertq.py captions --post-id <storebatch post id>`.\n"
    ra.write_new(stem + ".png", buf.getvalue())
    ra.write_new(stem + ".json", json.dumps(meta, indent=1, ensure_ascii=False).encode())
    ra.write_new(stem + ".md", md.encode())
    stem = os.path.abspath(stem)
    print(json.dumps({"png": stem + ".png", "json": stem + ".json", "md": stem + ".md"}))


if __name__ == "__main__":
    try:
        main()
    except cap.AlertTextError as e:
        sys.exit(f"refused: {e}")
