#!/usr/bin/env node
// Layout guard for the built site (local only; not run in the Actions workflow).
// Serves site/ the way GitHub Pages does, opens every page at 390px and 1280px wide,
// and fails (exit 1) if a page scrolls sideways, something sticks out past the screen edge,
// the main column and the sidebar overlap, or a table needs side-scrolling on desktop.
//
// Run after `python3 scripts/build_site.py`:
//   npm i --no-save playwright-core      (once; or point NODE_PATH at an existing install)
//   node scripts/check_layout.js [--shots DIR] [--chrome /path/to/chrome]
// Uses the system Chrome (/usr/bin/google-chrome) unless --chrome or CHROME is given.
const http = require("http"), fs = require("fs"), path = require("path");
const { chromium } = require("playwright-core");

const SITE = path.join(__dirname, "..", "site");
const args = process.argv.slice(2);
const opt = k => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; };
const SHOTS = opt("--shots");
const CHROME = opt("--chrome") || process.env.CHROME || "/usr/bin/google-chrome";
const WIDTHS = [390, 1280];
const TYPES = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".woff2": "font/woff2", ".xml": "application/xml" };

// GitHub Pages lookup: exact file, then .html, then dir/index.html, else 404.html
function resolve(urlPath) {
  const p = path.join(SITE, decodeURIComponent(urlPath.split("?")[0]));
  if (!p.startsWith(SITE)) return null;
  for (const c of [p, p + ".html", path.join(p, "index.html")])
    if (fs.existsSync(c) && fs.statSync(c).isFile()) return c;
  return null;
}
function pages() {
  const out = [];
  (function walk(d) {
    for (const f of fs.readdirSync(d)) {
      const p = path.join(d, f);
      if (fs.statSync(p).isDirectory()) { if (f !== "assets" && f !== "data") walk(p); }
      else if (f.endsWith(".html") && !/http-equiv="refresh"/i.test(fs.readFileSync(p, "utf8")))  // skip redirect stubs
        out.push("/" + path.relative(SITE, p).replace(/index\.html$/, "").replace(/\.html$/, ""));
    }
  })(SITE);
  return out.sort();
}

// Runs inside the page; returns a list of problems.
function inspect(width) {
  const probs = [], de = document.documentElement;
  if (de.scrollWidth > de.clientWidth + 1) probs.push(`page scrolls sideways (${de.scrollWidth}px wide in a ${de.clientWidth}px window)`);
  const scrollsInside = el => { for (let p = el.parentElement; p; p = p.parentElement) {
    const o = getComputedStyle(p).overflowX; if (o === "auto" || o === "scroll" || o === "hidden") return true; } return false; };
  const label = el => el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + (el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).join(".") : "");
  let n = 0;
  for (const el of document.body.querySelectorAll("*")) {
    const r = el.getBoundingClientRect();
    if (!r.width || getComputedStyle(el).position === "fixed" || el.closest(".sr")) continue;
    if ((r.right > de.clientWidth + 1 || r.left < -1) && !scrollsInside(el) && n++ < 5)
      probs.push(`${label(el)} sticks out past the screen edge (${Math.round(r.left)}..${Math.round(r.right)}px)`);
  }
  const main = document.querySelector(".layout > .main-col"), side = document.querySelector(".layout > .side-col");
  if (main && side && getComputedStyle(main).display !== "contents") {
    const a = main.getBoundingClientRect(), b = side.getBoundingClientRect();
    if (a.right > b.left + 1 && a.left < b.right && a.bottom > b.top && a.top < b.bottom) probs.push("main column overlaps the sidebar");
    for (const col of [main, side]) for (const c of col.children) {
      const r = c.getBoundingClientRect(), box = col.getBoundingClientRect();
      if (r.right > box.right + 1) probs.push(`${label(c)} is wider than its column`);
    }
  }
  if (width >= 1000) for (const t of document.querySelectorAll(".table-wrap"))
    if (t.scrollWidth > t.clientWidth + 1) probs.push(`table needs side-scrolling at ${width}px (${t.scrollWidth} > ${t.clientWidth})`);
  return probs;
}

(async () => {
  const server = http.createServer((req, res) => {
    const f = resolve(req.url) || path.join(SITE, "404.html");
    res.writeHead(f.endsWith("404.html") && !req.url.startsWith("/404") ? 404 : 200, { "content-type": TYPES[path.extname(f)] || "application/octet-stream" });
    fs.createReadStream(f).pipe(res);
  }).listen(0);
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ executablePath: CHROME });
  if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });
  let failed = 0;
  for (const w of WIDTHS) {
    const page = await browser.newPage({ viewport: { width: w, height: 900 } });
    page.on("pageerror", e => { console.log(`  JS error: ${e.message}`); failed++; });
    for (const p of pages()) {
      await page.goto(base + p, { waitUntil: "load" });
      await page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise(r => setTimeout(r, 40)); } scrollTo(0, 0); });
      await page.evaluate(() => document.fonts.ready);
      const probs = await page.evaluate(inspect, w);
      console.log(`${probs.length ? "FAIL" : "ok  "} ${w}px ${p}`);
      for (const m of probs) console.log("     - " + m);
      failed += probs.length;
      if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${(p.replace(/^\/|\/$/g, "") || "home").replace(/\//g, "_")}-${w}.png`), fullPage: true });
    }
    await page.close();
  }
  await browser.close(); server.close();
  console.log(failed ? `\n${failed} layout problem(s)` : "\nNo layout problems");
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
