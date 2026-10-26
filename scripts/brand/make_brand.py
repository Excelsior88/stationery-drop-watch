"""Generate Stationery Drop Watch brand assets (SVG + PNG) into site/assets/brand/.
Run: python3 scripts/brand/make_brand.py   (needs rsvg-convert, uharfbuzz, fonttools; font: Newsreader)"""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from textpath import text_path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "site", "assets", "brand")
FONT = "/usr/share/fonts/truetype/sand-box/google/Newsreader/Newsreader-VariableFont_opsz,wght.ttf"
VAR = {"wght": 520, "opsz": 40}
INK, TERRA, SAGE, CREAM, PAGE = "#2d2a32", "#c1553b", "#5f8a6b", "#fbf6ec", "#fffdf8"
GAP = 1.6
SW = 2.4  # one stroke width for the whole icon (64-unit grid)

# ---- icon geometry (64x64 grid) -------------------------------------------------
# notebook body
BX, BY, BW, BH, R = 10, 18, 34, 38, 4
BELL_CX, BELL_LIP = 47, 22.5

def bell_path(cx, lip, grow=0.0):
    """Bell silhouette: dome + flared lip. grow>0 inflates it (used for the gap mask)."""
    g = grow
    w_top, w_lip, h = 5.0 + g, 8.0 + g, 11.0 + g
    top = lip - h
    return (f"M{cx-w_lip:.2f} {lip+g:.2f} "
            f"C{cx-w_lip+1.8:.2f} {lip-1.0:.2f} {cx-w_top:.2f} {lip-2.6:.2f} {cx-w_top:.2f} {top+w_top:.2f} "
            f"A{w_top:.2f} {w_top:.2f} 0 0 1 {cx+w_top:.2f} {top+w_top:.2f} "
            f"C{cx+w_top:.2f} {lip-2.6:.2f} {cx+w_lip-1.8:.2f} {lip-1.0:.2f} {cx+w_lip:.2f} {lip+g:.2f} Z")


def _bez(p0, p1, p2, p3, n=24):
    return [tuple((1-t)**3*a + 3*(1-t)**2*t*b + 3*(1-t)*t*t*c + t**3*d for a, b, c, d in zip(p0, p1, p2, p3))
            for t in (i / n for i in range(n + 1))]

def gap_path(sw):
    """Bell + clapper + knob silhouette, offset outward by stroke/2 + GAP, as SVG path data."""
    import math
    from shapely.geometry import Polygon, Point
    from shapely.ops import unary_union
    cx, lip = BELL_CX, BELL_LIP
    wt, wl, h = 5.0, 8.0, 11.0
    top = lip - h
    pts = _bez((cx-wl, lip), (cx-wl+1.8, lip-1.0), (cx-wt, lip-2.6), (cx-wt, top+wt))
    pts += [(cx - wt*math.cos(a), top+wt - wt*math.sin(a)) for a in (math.pi*i/40 for i in range(1, 40))]
    pts += _bez((cx+wt, top+wt), (cx+wt, lip-2.6), (cx+wl-1.8, lip-1.0), (cx+wl, lip))
    shape = unary_union([Polygon(pts), Point(cx, lip+2.3).buffer(1.8, 64), Point(cx, lip-11.9).buffer(1.4, 64)])
    g = shape.buffer(sw/2 + GAP, 64)
    c = list(g.exterior.coords)
    return "M" + " L".join(f"{x:.3f} {y:.3f}" for x, y in c) + " Z"

def icon_group(small=False, uid="i"):
    """Return (defs, body) SVG fragments for the icon on the 64 grid."""
    sw = 4 if small else SW
    x0, y0, x1, y1 = BX, BY, BX + BW, BY + BH
    band_h = 8.5
    defs = f'''<clipPath id="{uid}gap" clipPathUnits="userSpaceOnUse"><path clip-rule="evenodd" d="M-20 -20 H84 V84 H-20 Z {gap_path(sw)}"/></clipPath>
  <clipPath id="{uid}clip"><rect x="{x0}" y="{y0}" width="{BW}" height="{BH}" rx="{R}"/></clipPath>'''
    lines = ""
    ly = [33, 39, 45] if not small else [34, 43]
    for i, y in enumerate(ly):
        xe = x1 - 6 if i < len(ly) - 1 or small else x1 - 12
        lines += f'<line x1="{x0+11}" y1="{y}" x2="{xe}" y2="{y}"/>'
    rings = "" if small else "".join(
        f'<circle cx="{cx}" cy="{y0+band_h/2+0.3}" r="1.9" fill="{PAGE}" stroke="{INK}" stroke-width="1.8"/>'
        for cx in (x0 + 13, x0 + 21))
    rib_x, rib_w, rib_bot = x0 + 11, 7, y1 + 7
    ribbon = (f'<path d="M{rib_x} {y1-2} H{rib_x+rib_w} V{rib_bot} L{rib_x+rib_w/2} {rib_bot-3.6} L{rib_x} {rib_bot} Z" '
              f'fill="{TERRA}"/>')
    notebook = f'''<g clip-path="url(#{uid}gap)">
    {ribbon}
    <g clip-path="url(#{uid}clip)">
      <rect x="{x0}" y="{y0}" width="{BW}" height="{BH}" fill="{PAGE}"/>
      <rect x="{x0}" y="{y0}" width="{BW}" height="{band_h}" fill="{TERRA}"/>
      <rect x="{x0}" y="{y0}" width="6" height="{BH}" fill="{INK}"/>
    </g>
    <rect x="{x0}" y="{y0}" width="{BW}" height="{BH}" rx="{R}" fill="none" stroke="{INK}" stroke-width="{sw}"/>
    {rings}
    <g stroke="{SAGE}" stroke-width="{sw}" stroke-linecap="round">{lines}</g>
  </g>'''
    clock = "" if small else (f'<path d="M{BELL_CX} {BELL_LIP-8.2} V{BELL_LIP-4.9} H{BELL_CX+2.6}" fill="none" '
                              f'stroke="{SAGE}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>')
    bell = f'''<g>
    <circle cx="{BELL_CX}" cy="{BELL_LIP+2.3}" r="1.8" fill="{TERRA}"/>
    <path d="{bell_path(BELL_CX, BELL_LIP)}" fill="{PAGE if not small else TERRA}" stroke="{TERRA}" stroke-width="{sw}" stroke-linejoin="round"/>
    <circle cx="{BELL_CX}" cy="{BELL_LIP-11.9}" r="1.4" fill="{TERRA}"/>
    {clock}
  </g>'''
    return defs, notebook + "\n  " + bell

# bbox of icon artwork on the 64 grid (incl. strokes): x 7.5..58.5, y 5.9..63.5
ICON_BBOX = (BX - SW/2, BELL_LIP - 11.9 - 1.4, BELL_CX + 8 + SW/2, BY + BH + 7)

def centered(transform_size, pad, small=False, uid="i"):
    x0, y0, x1, y1 = ICON_BBOX
    w, h = x1 - x0, y1 - y0
    s = (transform_size - 2 * pad) / max(w, h)
    tx = transform_size / 2 - s * (x0 + w / 2)
    ty = transform_size / 2 - s * (y0 + h / 2)
    d, b = icon_group(small, uid)
    return d, f'<g transform="translate({tx:.3f} {ty:.3f}) scale({s:.4f})">{b}</g>'

def svg(w, h, defs, body, bg=None, title="Stationery Drop Watch"):
    bgr = f'<rect width="{w}" height="{h}" fill="{bg}"/>' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{title}"><title>{title}</title><defs>{defs}</defs>{bgr}{body}</svg>\n')

def lockup(bg=None):
    # icon scaled to full height, left edge flush; wordmark optically centred on the notebook body
    H = 64
    x0, y0, x1, y1 = ICON_BBOX
    s = H / (y1 - y0)
    d, b = icon_group(uid="l")
    icon = f'<g transform="translate({-x0*s:.3f} {-y0*s:.3f}) scale({s:.4f})">{b}</g>'
    iw = (x1 - x0) * s
    size = 29
    tx = iw + 9
    base = 43
    p1, w1 = text_path(FONT, "Stationery", size, tx, base, VAR)
    p2, w2 = text_path(FONT, "Drop Watch", size, tx + w1 + size * 0.25, base, VAR)
    W = round(tx + w1 + size * 0.25 + w2 + 1)
    body = (icon + f'<path d="{p1}" fill="{INK}"/><path d="{p2}" fill="{TERRA}"/>')
    return W, H, d, body

def write(name, text):
    with open(os.path.join(OUT, name), "w") as f: f.write(text)

def png(src, dst, w, h=None):
    cmd = ["rsvg-convert", "-w", str(w)] + (["-h", str(h)] if h else []) + [os.path.join(OUT, src), "-o", os.path.join(OUT, dst)]
    subprocess.run(cmd, check=True)

def main():
    os.makedirs(OUT, exist_ok=True)
    W, H, d, body = lockup()
    write("logo.svg", svg(W, H, d, body))
    # cream PNG of lockup with margin
    m = 10
    write("_logo_cream.svg", svg(W + 2*m, H + 2*m, d, f'<g transform="translate({m} {m})">{body}</g>', bg=CREAM))
    d, b = centered(64, 2); write("icon.svg", svg(64, 64, d, b))
    d, b = centered(64, 1, small=True, uid="f"); write("favicon.svg", svg(64, 64, d, b))
    d, b = centered(1080, 165, uid="a"); write("_avatar.svg", svg(1080, 1080, d, b, bg=CREAM))
    d, b = centered(180, 22, uid="t"); write("_touch.svg", svg(180, 180, d, b, bg=CREAM))
    png("favicon.svg", "favicon-32.png", 32)
    png("_touch.svg", "apple-touch-icon.png", 180)
    png("icon.svg", "icon-512.png", 512)
    png("_avatar.svg", "avatar-1080.png", 1080)
    png("_logo_cream.svg", "logo-1600.png", 1600)
    for f in ("_logo_cream.svg", "_avatar.svg", "_touch.svg"): os.remove(os.path.join(OUT, f))
    print("ok", W, H)

if __name__ == "__main__":
    main()
