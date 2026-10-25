import sys
from playwright.sync_api import sync_playwright
port = open(".port").read().strip()
base = f"http://127.0.0.1:{port}/"
shots = [("index.html", "home", [(1440, 900, "desktop"), (390, 844, "mobile")]),
         ("hobonichi-2027.html", "hobonichi-2027", [(1440, 900, "desktop"), (390, 844, "mobile")])]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    for path, name, sizes in shots:
        for w, h, tag in sizes:
            ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if tag == "mobile" else 1, is_mobile=(tag == "mobile"), has_touch=(tag == "mobile"))
            pg = ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.goto(base + path, wait_until="networkidle")
            pg.wait_for_timeout(300)
            out = f"screenshots/{name}-{tag}.png"
            pg.screenshot(path=out, full_page=True)
            print(out, "console errors:", errs)
            ctx.close()
    b.close()
