"""X header banner (1500x500): site/assets/brand/x-header.svg + x-header-1500x500.png.
Safe zone: X puts the avatar over roughly the left 400px / bottom 200px; phones crop ~60px top and bottom.
Run: python3 scripts/brand/make_x_header.py"""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from textpath import text_path
from make_brand import OUT, INK, TERRA, SAGE, CREAM, PAGE, bell_path

G = "/usr/share/fonts/truetype/sand-box/google/"
SERIF = G + "Newsreader/Newsreader-VariableFont_opsz,wght.ttf"
SERIF_I = G + "Newsreader/Newsreader-Italic-VariableFont_opsz,wght.ttf"
SANS = G + "Inter/" + sorted(f for f in os.listdir(G + "Inter") if "Italic" not in f)[0]
MUSTARD, INK2, LINE = "#c99a2e", "#5b5560", "#e6dccb"
W, H = 1500, 500

def build():
    parts = []
    # planner-paper dot grid, faint
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="1.6"/>' for x in range(30, W, 30) for y in range(20, H, 30))
    parts.append(f'<g fill="{LINE}">{dots}</g>')
    # text block, left-aligned, centred in the safe area (x 520..1420, y 60..440)
    X = 520
    head_size = 92
    p1, w1 = text_path(SERIF, "Never miss a ", head_size, X, 226, {"wght": 520, "opsz": 72})
    p2, w2 = text_path(SERIF_I, "restock.", head_size, X + w1, 226, {"wght": 520, "opsz": 72})
    parts.append(f'<path d="{p1}" fill="{INK}"/><path d="{p2}" fill="{TERRA}"/>')
    # mustard underline accent beneath "restock."
    ux0, ux1 = X + w1 + 6, X + w1 + w2 - 22
    parts.append(f'<path d="M{ux0:.1f} 250 Q{(ux0+ux1)/2:.1f} 242 {ux1:.1f} 248" fill="none" stroke="{MUSTARD}" '
                 f'stroke-width="5" stroke-linecap="round"/>')
    sub = "Hobonichi Techo 2027 planners & covers, checked hourly across 13 shops."
    p3, w3 = text_path(SERIF, sub, 28, X + 2, 306, {"wght": 420, "opsz": 24})
    parts.append(f'<path d="{p3}" fill="{INK2}"/>')
    url = "excelsior88.github.io/stationery-drop-watch"
    p4, w4 = text_path(SANS, url, 19, X + 2 + 30, 368, {"wght": 500}, tracking=0.01)
    # small bell before the url (logo motif), sage clock hands
    s, bx, by = 1.25, X + 14, 356
    bell = (f'<g transform="translate({bx} {by}) scale({s}) translate(-47 -17)">'
            f'<circle cx="47" cy="19.3" r="1.8" fill="{TERRA}"/>'
            f'<path d="{bell_path(47, 17)}" fill="{PAGE}" stroke="{TERRA}" stroke-width="2.4" stroke-linejoin="round"/>'
            f'<circle cx="47" cy="5.1" r="1.4" fill="{TERRA}"/></g>')
    parts.append(bell + f'<path d="{p4}" fill="{TERRA}"/>')
    width = max(w1 + w2, w3 + 2)
    # faint sage ruled lines, like a planner page, in the clear top-left area (above the avatar zone)
    lines = "".join(f'<line x1="70" y1="{y}" x2="{380 if i < 3 else 300}" y2="{y}"/>' for i, y in enumerate((120, 156, 192, 228)))
    parts.append(f'<g stroke="{SAGE}" stroke-opacity=".28" stroke-width="4" stroke-linecap="round">{lines}</g>')
    # terracotta bookmark ribbon hanging from the top edge, far right
    rbx, rw, rb = W - 92, 34, 150
    parts.append(f'<path d="M{rbx} 0 H{rbx+rw} V{rb} L{rbx+rw/2} {rb-16} L{rbx} {rb} Z" fill="{TERRA}"/>')
    return "".join(parts), width

def main():
    body, width = build()
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'aria-label="Stationery Drop Watch: Never miss a restock."><rect width="{W}" height="{H}" fill="{CREAM}"/>{body}</svg>\n')
    open(os.path.join(OUT, "x-header.svg"), "w").write(svg)
    subprocess.run(["rsvg-convert", os.path.join(OUT, "x-header.svg"), "-o", os.path.join(OUT, "x-header-1500x500.png")], check=True)
    print("text block width", round(width))

if __name__ == "__main__":
    main()
