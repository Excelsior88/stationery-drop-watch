#!/usr/bin/env python3
"""Build the static site in site/ from stores.json, data/*.json and content/*.json.
Never invents data: every status shown comes from data/stock.json written by checker.py."""
import json, html, re, datetime as dt, shutil
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ET = ZoneInfo("America/New_York")
E = html.escape

# Amazon Associates tracking ID. Every amazon.com product link on the site is rewritten to
# https://www.amazon.com/dp/<ASIN>?tag=<AMAZON_TAG> with rel="sponsored noopener" (see tag_amazon_links).
AMAZON_TAG = "excelsior88-20"
AMAZON_DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."
_ASIN = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})")
_AMAZON_A = re.compile(r'<a\b[^>]*\bhref="https?://(?:www\.)?amazon\.com/[^"]*"[^>]*>')

def amazon_link(url):
    """Clean, tagged Amazon product URL; non-product Amazon URLs just get the tag added."""
    m = _ASIN.search(url)
    if m:
        return f"https://www.amazon.com/dp/{m.group(1)}?tag={AMAZON_TAG}"
    base = re.sub(r"([?&])tag=[^&]*&?", r"\1", url).rstrip("?&")
    return f"{base}{'&' if '?' in base else '?'}tag={AMAZON_TAG}"

def tag_amazon_links(doc):
    """Final pass over a rendered page: tag every amazon.com link and mark it sponsored."""
    def fix(m):
        a = m.group(0)
        href = html.unescape(re.search(r'href="([^"]*)"', a).group(1))
        a = re.sub(r'href="[^"]*"', f'href="{E(amazon_link(href))}"', a)
        a = re.sub(r'\s(rel|data-todo)="[^"]*"', "", a)
        return a.replace("<a ", '<a rel="sponsored noopener" ', 1)
    return _AMAZON_A.sub(fix, doc)

stores = json.loads((ROOT / "stores.json").read_text())
stock = json.loads((ROOT / "data/stock.json").read_text())
changes = json.loads((ROOT / "data/changes.json").read_text())
picks = json.loads((ROOT / "content/editor_picks.json").read_text())

def fmt_et(iso):
    t = dt.datetime.fromisoformat(iso).astimezone(ET)
    return t.strftime("%b %-d, %Y, %-I:%M %p ") + t.tzname()

STATUS = {"in_stock": "In stock", "preorder": "Preorder", "coming_soon": "Not yet on sale",
          "sold_out": "Sold out", "unknown": "Couldn't check"}
NAV = [("index.html", "Restock tracker"), ("hobonichi-2027.html", "Hobonichi 2027 calendar"), ("about.html", "About")]

def page(fname, title, desc, body):
    return tag_amazon_links(_page(fname, title, desc, body))

def _page(fname, title, desc, body):
    nav = "".join(f'<a href="{h}"{" aria-current=page" if h == fname else ""}>{E(t)}</a>' for h, t in NAV)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title><meta name="description" content="{E(desc)}">
<link rel="stylesheet" href="assets/style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📓</text></svg>">
</head><body>
<header class="masthead"><div class="wrap">
  <a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true">✦</span> Stationery Drop Watch</a>
  <nav>{nav}</nav>
</div></header>
<main class="wrap">{body}</main>
<footer class="foot"><div class="wrap">
  <p><strong>Stationery Drop Watch</strong> checks independent and official stores for limited planner restocks so you don't have to refresh ten tabs.</p>
  <p class="muted">Statuses come straight from each store's public product data at the time shown. Always confirm on the store's page before you plan around it. Some links may become affiliate links; we'll label them when they do.</p>
  <p class="disclosure">{E(AMAZON_DISCLOSURE)}</p>
  <!-- TODO(affiliate): replace these with tracked links once each program approves the site -->
  <p class="partners">Notebooks we like: <a href="https://www.leuchtturm1917.com/" data-todo="affiliate-leuchtturm1917" rel="nofollow">Leuchtturm1917</a> · <a href="https://baronfig.com/" data-todo="affiliate-baronfig" rel="nofollow">Baron Fig</a> · <a href="https://stationerypal.com/" data-todo="affiliate-stationerypal" rel="nofollow">Stationery Pal</a> <span class="todo-chip" title="Affiliate links not set up yet">TODO: affiliate</span></p>
</div></footer>
<script src="assets/app.js" defer></script>
</body></html>"""

NEWSLETTER = "dropwatch"  # Buttondown username (https://buttondown.com/dropwatch)

def signup_block(compact=False):
    # Buttondown's standard HTML embed form (docs.buttondown.com/building-your-subscriber-base):
    # a plain POST to embed-subscribe; don't submit via fetch, Buttondown may need to show a CAPTCHA.
    return f"""<section class="card signup{' compact' if compact else ''}" id="alerts">
  <h2>Get restock alerts</h2>
  <p>One short email when a sold-out Hobonichi item comes back somewhere we track. No spam, unsubscribe anytime.</p>
  <form class="signup-form embeddable-buttondown-form" action="https://buttondown.com/api/emails/embed-subscribe/{NEWSLETTER}" method="post">
    <label class="sr" for="email{int(compact)}">Email address</label>
    <input id="email{int(compact)}" type="email" name="email" placeholder="you@example.com" required autocomplete="email">
    <input type="hidden" value="1" name="embed">
    <button type="submit">Notify me</button>
  </form>
  <p class="form-note">Sent via <a href="https://buttondown.com/{NEWSLETTER}" target="_blank" rel="noopener">Buttondown</a>.</p>
</section>"""

def sponsor_block():
    # TODO(sponsor): when a shop books this slot, replace the placeholder with their logo, line, and link (rel="sponsored").
    return """<aside class="card sponsor" aria-label="Featured shop">
  <p class="eyebrow">Featured shop</p>
  <div class="sponsor-slot">
    <p class="sponsor-title">This spot is available</p>
    <p>Run an independent stationery shop? Put your next restock in front of planner people who are actively hunting for it.</p>
    <a class="btn-ghost" href="about.html#sponsor">Sponsor details</a>
  </div>
</aside>"""

def editor_block():
    items = []
    for b in picks["books"]:
        details = "".join(f"<li>{E(d)}</li>" for d in b.get("details", []))
        items.append(f"""<article class="book" data-book-id="{E(b['id'])}">
  <a class="book-cover" href="{E(amazon_link(b['url']))}" rel="sponsored noopener" target="_blank">
    <img src="{E(b['cover'])}" alt="{E(b['cover_alt'])}" width="200" height="300" loading="lazy"></a>
  <div class="book-body">
    <p class="eyebrow">{E(b.get('kicker',''))}</p>
    <h3>{E(b['pitch'])}</h3>
    <p class="book-title">{E(b['title'])} <span class="muted">· {E(b.get('format',''))}</span></p>
    <p>{E(b['blurb'])}</p>
    <ul class="book-details">{details}</ul>
    <a class="btn" href="{E(amazon_link(b['url']))}" rel="sponsored noopener" target="_blank">See it on Amazon</a>
  </div>
</article>""")
    return f"""<section class="card editor" aria-label="{E(picks['heading'])}">
  <p class="eyebrow">{E(picks['heading'])}</p>
  <div class="books">{''.join(items)}</div>
  <p class="muted small">Made by the person who runs this site.</p>
</section>"""

def build_index():
    prods = stock["products"]
    s = stock["summary"]
    checked = sum(v for k, v in s.items() if k != "unknown")
    restocks = [c for c in changes if c["to"] in ("in_stock", "preorder") and c["from"] in ("sold_out", "coming_soon")]
    restocks.sort(key=lambda c: c["at"], reverse=True)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)
    recent = [c for c in restocks if dt.datetime.fromisoformat(c["at"]) >= cutoff][:12]
    if recent:
        feed = "".join(f"""<li class="feed-item"><span class="badge {E(c['to'])}">{E(STATUS[c['to']])}</span>
  <a href="{E(c['url'])}" rel="noopener" target="_blank">{E(c['label'])}</a> <span class="muted">at {E(c['store'])}</span>
  <time datetime="{E(c['at'])}">{E(fmt_et(c['at']))}</time></li>""" for c in recent)
        feed_html = f'<ol class="feed">{feed}</ol>'
    else:
        feed_html = f"""<div class="empty"><p><strong>No restocks spotted yet.</strong> Tracking started {E(fmt_et(stock['run_started']))}.
  A restock shows up here the moment a sold-out item flips back to in stock or preorder between two checks.</p>
  <p class="muted">Right now: {s['sold_out']} tracked listings are sold out and {s['coming_soon']} aren't on sale yet. Those are the ones we're watching.</p></div>"""

    # table data (embedded so the page works without fetch)
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    rows = [dict(p=p["label"], c=p.get("canonical") or "", t=p["type"], s=p["store"], sid=p["store_id"], st=p["status"],
                 u=p["url"], at=p["checked_at"], since=p.get("status_since"), title=p.get("title") or "",
                 va=p.get("available_variants"), tv=p.get("total_variants")) for p in prods]
    store_opts = "".join(f'<option value="{E(x["id"])}">{E(x["name"])}</option>' for x in stores["stores"] if x["platform"] in ("shopify", "hobonichi"))
    prod_opts = "".join(f'<option value="{E(k)}">{E(v)}</option>' for k, v in canon.items() if any(p.get("canonical") == k for p in prods))
    type_opts = "".join(f'<option value="{E(t)}">{E(t)}</option>' for t in sorted({p["type"] for p in prods}))
    status_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in STATUS.items() if any(p["status"] == k for p in prods))
    not_checked = "".join(f'<li><a href="{E(n["url"])}" rel="noopener" target="_blank">{E(n["name"])}</a>: <span class="muted">{E(n["reason"] or "")}</span></li>' for n in stock["not_checked"])

    noscript_rows = "".join(f'<tr><td>{E(r["p"])}</td><td>{E(r["s"])}</td><td><span class="badge {r["st"]}">{STATUS[r["st"]]}</span></td></tr>' for r in rows)
    body = f"""
<section class="hero">
  <p class="eyebrow">Hobonichi Techo 2027 · {len({p['store_id'] for p in prods})} stores checked</p>
  <h1>Know the moment your planner is back.</h1>
  <p class="lede">We check the official Hobonichi store and independent shops for sold-out planners and covers, and tell you when they come back.</p>
  <div class="stats">
    <div><b>{s['in_stock']}</b><span>in stock</span></div>
    <div><b>{s['preorder']}</b><span>preorder</span></div>
    <div><b>{s['sold_out']}</b><span>sold out</span></div>
    <div><b>{s['coming_soon']}</b><span>not yet on sale</span></div>
  </div>
  <p class="muted small">Last check: <time datetime="{E(stock['run_finished'])}">{E(fmt_et(stock['run_finished']))}</time> · {checked} of {len(prods)} listings checked successfully.</p>
</section>

<div class="layout">
  <div class="main-col">
    <section class="card" id="restocked">
      <h2>Restocked recently</h2>
      {feed_html}
    </section>

    <section class="card" id="tracker">
      <div class="section-head"><h2>Every listing we track</h2><p class="muted small" id="count"></p></div>
      <form class="filters" onsubmit="return false">
        <label>Product<select id="f-product"><option value="">All products</option>{prod_opts}<option value="__other">Other 2027 items</option></select></label>
        <label>Type<select id="f-type"><option value="">All types</option>{type_opts}</select></label>
        <label>Store<select id="f-store"><option value="">All stores</option>{store_opts}</select></label>
        <label>Status<select id="f-status"><option value="">Any status</option>{status_opts}</select></label>
        <label class="grow">Search<input id="f-q" type="search" placeholder="Moomin, Cousin, Midnight Blue…"></label>
      </form>
      <div class="table-wrap"><table class="stock">
        <thead><tr><th>Product</th><th>Store</th><th>Status</th><th class="hide-sm">Checked</th></tr></thead>
        <tbody id="rows"><noscript>{noscript_rows}</noscript></tbody>
      </table></div>
      <button type="button" id="more" class="btn-ghost more" hidden>Show all</button>
      <p class="muted small">"Not yet on sale" means the store has a preview page up but isn't taking orders yet.</p>
      <details class="muted small"><summary>Stores we list but don't check automatically</summary><ul>{not_checked}</ul></details>
    </section>
  </div>
  <aside class="side-col">
    {signup_block(compact=True)}
    {sponsor_block()}
    {editor_block()}
    <section class="card soon">
      <p class="eyebrow">Coming to the tracker</p>
      <ul><li>Traveler's Company limited editions</li><li>MIDORI MD seasonal releases</li><li>Leuchtturm1917 special editions</li></ul>
    </section>
  </aside>
</div>
<script id="stock-data" type="application/json">{json.dumps(rows, ensure_ascii=False).replace('</', '<\\/')}</script>
"""
    return page("index.html", "Stationery Drop Watch: Hobonichi 2027 restock tracker",
                "Live restock and sold-out status for Hobonichi Techo 2027 planners and covers across the official store and independent shops.", body)

def build_hobonichi():
    body = """
<article class="prose">
<p class="eyebrow">Guide · updated Oct 25, 2026</p>
<h1>Hobonichi Techo 2027: launch &amp; restock calendar</h1>
<p class="lede">Hobonichi sells its planners in two big drops a year, and popular covers can sell out within minutes. Here's how the 2027 season has gone so far and when stock usually comes back.</p>

<ol class="timeline">
  <li><time>Aug 25, 2026</time><div><h3>Previews go up</h3><p>Shops post the 2027 lineup as "out of stock" or "coming soon" pages. They aren't sold out; they're just not on sale yet. <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Aug 31, 2026 · 10 PM ET</time><div><h3>Worldwide launch (January-start planners)</h3><p>Everything goes live at the same moment worldwide: 11 AM on September 1 in Japan, 10 PM ET / 9 PM CT the night before in the US. Atlas Stationers warned that popular styles and collaborations "often sell out within minutes." <a href="#s-papermouse">[Paper Mouse]</a> <a href="#s-atlas">[Atlas]</a></p></div></li>
  <li><time>Sep 30 – Oct 1, 2026</time><div><h3>Second fall wave</h3><p>Hobonichi notes that some products begin sales on October 1. At US shops that meant the ONE PIECE magazine collection and the Weeksdays 2027 desk calendar, plus a large restock of earlier sell-outs (as preorders at some shops). <a href="#s-1101">[Hobonichi]</a> <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Early–mid Oct 2026</time><div><h3>First restocks land at indie shops</h3><p>Atlas expected its first restock in early October. Paper Mouse's shipment arrived October 15 and preorders began shipping. <a href="#s-atlas">[Atlas]</a> <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Through December</time><div><h3>Last call for dated 2027 books</h3><p>Paper Mouse says it doesn't usually restock dated planners after December, so whatever is left is all that's left. <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>February 2027</time><div><h3>Spring launch (April-start planners)</h3><p>The second yearly release, timed to Japan's April academic and fiscal year. Expect another rush on new covers. <a href="#s-papermouse">[Paper Mouse]</a> <a href="#s-1101">[Hobonichi]</a></p></div></li>
</ol>

<h2>Will it come back?</h2>
<p>Usually, but not always. Standard planner books and core colors tend to be restocked. Special collaborations may only be sold at launch <a href="#s-atlas">[Atlas]</a>. Paper Mouse says almost every item has been restocked at least once after launch in past years <a href="#s-papermouse">[Paper Mouse]</a>. Hobonichi's own restock emails are only for the Techo books and the Drawer Pouch, not accessories, and they don't promise you'll get one <a href="#s-1101">[Hobonichi]</a>.</p>

<h2>How to not miss it</h2>
<ul>
  <li>Check several shops. When one store sells out, another often still has stock. That's the whole point of the <a href="index.html#tracker">tracker</a>.</li>
  <li>Buying direct from Hobonichi is the only way to get store-exclusive extras, but it ships from Japan and tariffs may apply in the US <a href="#s-papermouse">[Paper Mouse]</a>.</li>
  <li><a href="#alerts">Sign up for alerts</a> and we'll email you when something flips back to in stock.</li>
</ul>
""" + signup_block() + """
<h2>Sources</h2>
<ol class="sources">
  <li id="s-1101"><a href="https://www.1101.com/store/techo/en/2027/pc/shopping_guide/" rel="noopener" target="_blank">Hobonichi Techo 2027 shopping guide</a>, Hobonichi (official). Release dates, shipping, and restock notification rules.</li>
  <li id="s-papermouse"><a href="https://www.thepapermouse.com/pages/hobonichi-faq" rel="noopener" target="_blank">Hobonichi FAQ</a>, The Paper Mouse. Launch times, the Sept 30 preorder, the Oct 15 arrival, and restock history.</li>
  <li id="s-atlas"><a href="https://www.atlasstationers.com/blogs/news/hobonichi-faq-2027" rel="noopener" target="_blank">Hobonichi FAQ – 2027</a>, Atlas Stationers. Launch time, sell-out warning, and the early-October restock.</li>
</ol>
</article>"""
    return page("hobonichi-2027.html", "Hobonichi Techo 2027 launch & restock calendar · Stationery Drop Watch",
                "When Hobonichi Techo 2027 planners launch, sell out and restock, with sources.", body)

def build_about():
    n_checked = len([s for s in stores["stores"] if s["platform"] in ("shopify", "hobonichi")])
    body = f"""
<article class="prose">
<h1>About Stationery Drop Watch</h1>
<p class="lede">Limited planners sell out fast, and every shop only posts its own restocks. This site checks them all in one place.</p>
<h2>How it works</h2>
<p>A small script visits the public product pages of {n_checked} stores on a schedule, at a polite pace and following each store's robots.txt. It reads whether each listing can be bought right now. When a sold-out listing becomes available again, it shows up in <a href="index.html#restocked">Restocked recently</a> and goes out to the alert list.</p>
<p>We only show what the stores report. If a check fails, we say so instead of guessing.</p>
<h2 id="sponsor">Featured shop slot</h2>
<p>Independent stationery shops can book the featured spot on the tracker to promote a restock or launch. It's clearly labeled as sponsored. <span class="todo-chip">TODO: add a contact address and rates</span></p>
<h2>Affiliate links</h2>
<p>Some links to notebook brands may become affiliate links. If you buy through one, the site may earn a small commission at no extra cost to you. Store listings in the tracker are plain links.</p>
<h2>Contact</h2>
<p><span class="todo-chip">TODO: add a contact email</span></p>
</article>"""
    return page("about.html", "About · Stationery Drop Watch", "How Stationery Drop Watch tracks planner restocks.", body)

def main():
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "data/stock.json", SITE / "data/stock.json")
    shutil.copy(ROOT / "data/changes.json", SITE / "data/changes.json")
    (SITE / "index.html").write_text(build_index())
    (SITE / "hobonichi-2027.html").write_text(build_hobonichi())
    (SITE / "about.html").write_text(build_about())
    print("built", [p.name for p in SITE.glob("*.html")])

if __name__ == "__main__":
    main()
