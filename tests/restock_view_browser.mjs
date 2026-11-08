/** Drive the real restock controls in Chrome. Fixtures are synthetic HTML from restock_feed. */
import { createRequire } from "node:module";
const puppeteer = createRequire(import.meta.url)("puppeteer-core");

const chrome = process.env.CHROME || "/usr/local/bin/google-chrome";
const base = process.env.FIXTURE_ORIGIN;
const failures = [];

function check(name, ok, detail) {
  if (!ok) failures.push(name + ": " + detail);
  console.log((ok ? "ok  " : "FAIL ") + name + (detail ? " — " + detail : ""));
}

async function visible(page) {
  return page.evaluate(() => ({
    rows: [...document.querySelectorAll(".feed-item")].filter(el => getComputedStyle(el).display !== "none").map(el => el.getAttribute("data-now")),
    empty: getComputedStyle(document.querySelector(".feed-empty")).display !== "none",
    open: [...document.querySelectorAll("details")].map(el => el.open),
    controls: getComputedStyle(document.querySelector(".feed-controls")).display,
    times: [...document.querySelectorAll("time.time-instant")].map(el => el.textContent),
    datetimes: [...document.querySelectorAll("time.time-instant")].map(el => el.getAttribute("datetime")),
    note: document.querySelector(".time-zone-note")?.textContent || "",
  }));
}

async function run() {
  const browser = await puppeteer.launch({
    executablePath: chrome,
    headless: true,
    args: ["--no-sandbox", "--disable-gpu"],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1100, height: 900 });
    await page.emulateTimezone("Asia/Tokyo");
    await page.goto(base + "/mixed.html", { waitUntil: "networkidle0" });

    let state = await visible(page);
    check("js all rows", state.rows.length === 2 && state.rows.includes("sold_out") && state.rows.includes("in_stock"), JSON.stringify(state.rows));
    check("js disclosure starts closed", state.open.length === 1 && state.open[0] === false, JSON.stringify(state.open));
    check("js empty hidden on all", state.empty === false, String(state.empty));
    check("js converts visible and history times", state.times.every(t => t.includes("GMT+9") && !t.endsWith(" ET")), state.times.join(" | "));
    check("js keeps iso datetimes", state.datetimes.includes("2026-11-08T08:44:43+00:00") && state.datetimes.includes("2026-11-06T23:18:18+00:00"), state.datetimes.join(" | "));
    check("js zone note switched", state.note === "Times are labeled in your time zone.", state.note);

    await page.click("details summary");
    state = await visible(page);
    check("click opens history", state.open[0] === true, JSON.stringify(state.open));

    await page.click("input.restock-in");
    state = await visible(page);
    check("click in stock keeps only in_stock", JSON.stringify(state.rows) === '["in_stock"]' && state.empty === false, JSON.stringify(state));

    await page.click("input.restock-all");
    state = await visible(page);
    check("click all restores rows and open history", state.rows.length === 2 && state.open[0] === true && state.empty === false, JSON.stringify(state.rows) + " open=" + state.open);

    await page.focus("input.restock-all");
    await page.keyboard.press("ArrowRight");
    state = await visible(page);
    const inChecked = await page.$eval("input.restock-in", el => el.checked);
    check("arrow selects in stock", inChecked && JSON.stringify(state.rows) === '["in_stock"]', JSON.stringify(state.rows));
    await page.keyboard.press("ArrowLeft");
    state = await visible(page);
    check("arrow returns to all", state.rows.length === 2, JSON.stringify(state.rows));
    await page.focus("details summary");
    await page.keyboard.press("Enter");
    const toggled = await page.$eval("details", el => el.open);
    check("enter toggles disclosure", toggled === false, String(toggled));

    await page.goto(base + "/empty.html", { waitUntil: "networkidle0" });
    state = await visible(page);
    check("empty fixture all shows four non-stock rows", state.rows.length === 4 && !state.rows.includes("in_stock") && state.empty === false, JSON.stringify(state.rows));
    await page.click("input.restock-in");
    state = await visible(page);
    check("empty fixture in stock shows only the note", state.rows.length === 0 && state.empty === true, JSON.stringify(state));
    await page.click("input.restock-all");
    state = await visible(page);
    check("empty fixture all restores the four rows", state.rows.length === 4 && state.empty === false, JSON.stringify(state.rows));

    const plain = await browser.newPage();
    await plain.setJavaScriptEnabled(false);
    await plain.setViewport({ width: 390, height: 800 });
    await plain.goto(base + "/mixed.html", { waitUntil: "networkidle0" });
    state = await visible(plain);
    check("no-js times stay eastern", state.times.every(t => t.endsWith(" ET")), state.times.join(" | "));
    check("no-js note stays eastern", state.note === "Times are labeled Eastern Time.", state.note);
    check("no-js controls visible", state.controls === "flex", state.controls);
    await plain.click("input.restock-in");
    state = await visible(plain);
    check("no-js in stock filters", JSON.stringify(state.rows) === '["in_stock"]', JSON.stringify(state.rows));
    await plain.click("input.restock-all");
    state = await visible(plain);
    check("no-js all restores", state.rows.length === 2 && state.open[0] === false, JSON.stringify(state.rows));
    await plain.click("details summary");
    state = await visible(plain);
    check("no-js summary opens history", state.open[0] === true, JSON.stringify(state.open));
  } finally {
    await browser.close();
  }
  if (failures.length) {
    console.error(failures.join("\n"));
    process.exit(1);
  }
  console.log("browser restock view ok");
}

run().catch(err => { console.error(err); process.exit(1); });
