/** Drive the real shop-list and tracker filters in Chrome. The fixture is synthetic. */
import { createRequire } from "node:module";
const puppeteer = createRequire(import.meta.url)("puppeteer-core");

const chrome = process.env.CHROME || "/usr/local/bin/google-chrome";
const base = process.env.FIXTURE_ORIGIN;
const failures = [];

function check(name, ok, detail) {
  if (!ok) failures.push(name + ": " + detail);
  console.log((ok ? "ok  " : "FAIL ") + name + (detail ? " — " + detail : ""));
}

async function rows(page, sel) {
  return page.evaluate((sel) => [...document.querySelectorAll(sel)].map(tr => ({
    hidden: tr.hidden,
    store: tr.getAttribute("data-store"),
    status: tr.getAttribute("data-status"),
    text: tr.textContent.replace(/\s+/g, " ").trim(),
  })), sel);
}

async function run() {
  const browser = await puppeteer.launch({
    executablePath: chrome,
    headless: true,
    args: ["--no-sandbox", "--disable-gpu"],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 900 });
    await page.goto(base + "/list.html", { waitUntil: "networkidle0" });

    let state = await rows(page, "#stock tbody tr");
    check("list starts with every shop", state.length === 3 && state.every(r => !r.hidden), JSON.stringify(state));

    await page.focus("[data-filter=q]");
    await page.keyboard.type("sage");
    await page.waitForFunction(() => location.search.includes("q=sage"));
    state = await rows(page, "#stock tbody tr");
    check("search keeps the matching shop", state.filter(r => !r.hidden).length === 1 && state.find(r => !r.hidden).text.includes("Sage"), JSON.stringify(state));
    check("search writes the URL", (await page.evaluate(() => location.search)).includes("q=sage"), await page.evaluate(() => location.search));

    await page.select("[data-filter=status]", "sold_out");
    await page.waitForFunction(() => location.search.includes("status=sold_out"));
    state = await rows(page, "#stock tbody tr");
    check("status and search together can match nothing", state.every(r => r.hidden), JSON.stringify(state));
    check("empty note is visible", await page.$eval(".card-empty", el => !el.hidden), "");

    await page.click("[data-filter=reset]");
    await page.waitForFunction(() => !location.search);
    state = await rows(page, "#stock tbody tr");
    check("reset shows every shop", state.every(r => !r.hidden) && state.length === 3, JSON.stringify(state));

    await page.goBack();
    await page.waitForFunction(() => location.search.includes("status=sold_out"));
    state = await rows(page, "#stock tbody tr");
    check("back restores the empty filter", state.every(r => r.hidden), await page.evaluate(() => location.search));

    await page.goto(base + "/tracker.html", { waitUntil: "networkidle0" });
    await page.select("#f-status", "in_stock");
    await page.waitForFunction(() => location.search.includes("status=in_stock"));
    const count = await page.$eval("#count", el => el.textContent);
    check("tracker status filter counts the in-stock row", count.includes("1 of 1"), count);
    await page.focus("#f-q");
    await page.keyboard.type("no-such-notebook");
    await page.waitForFunction(() => document.querySelector(".empty-row"));
    check("tracker search empty state", !!(await page.$(".empty-row")), await page.$eval("#rows", el => el.textContent));
    await page.click("#f-reset");
    await page.waitForFunction(() => !location.search);
    check("tracker reset clears the URL", (await page.evaluate(() => location.search)) === "", await page.evaluate(() => location.search));

    await page.goto(base + "/fam.html", { waitUntil: "networkidle0" });
    const closed = await page.$$eval("details.fam-block", (els) => els.map((d) => ({ name: d.querySelector(".fam-name").textContent, open: d.open, meta: d.querySelector(".fam-meta").textContent })));
    check("families start collapsed with a stock count", closed.length === 2 && closed.every((d) => !d.open && /listings in stock/.test(d.meta)) && closed.some((d) => d.name === "Original A6"), JSON.stringify(closed));
    await page.focus("#f-q");
    await page.keyboard.type("Weeks");
    await page.waitForFunction(() => document.querySelectorAll("details.fam-block").length === 1 && document.querySelector("details.fam-block").open);
    check("search expands only the matching family", true, "");
    await page.click("#f-reset");
    await page.waitForFunction(() => document.querySelectorAll("details.fam-block").length === 2 && [...document.querySelectorAll("details.fam-block")].every((d) => !d.open));
    check("reset collapses every family", true, "");
    await page.goto(base + "/fam.html#original-a6-en", { waitUntil: "networkidle0" });
    const linked = await page.$eval("#original-a6", (d) => d.open && d.contains(document.getElementById("original-a6-en")));
    check("a link inside a family opens that family", linked, "");
  } finally {
    await browser.close();
  }
  if (failures.length) {
    console.error(failures.join("\n"));
    process.exit(1);
  }
  console.log("browser page filters ok");
}

run().catch(err => { console.error(err); process.exit(1); });
