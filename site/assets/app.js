// Stationery Drop Watch: client-side table filtering. The check time is shown once per table (build_site.py).
(function () {
  if (window.DropWatchTime) window.DropWatchTime.showLocalTimes(document);
  const mast = document.querySelector(".masthead");
  const filterBar = document.querySelector("#filters");
  if (mast || filterBar) {
    const pinMast = () => {
      if (mast) document.documentElement.style.setProperty("--mast", Math.ceil(mast.getBoundingClientRect().height) + "px");
      if (filterBar) document.documentElement.style.setProperty("--filter-h", Math.ceil(filterBar.getBoundingClientRect().height) + "px");
    };
    pinMast();
    window.addEventListener("resize", pinMast);
    if (filterBar && typeof ResizeObserver !== "undefined") new ResizeObserver(pinMast).observe(filterBar);
  }
  // The Hobonichi tracker moved from the homepage to its own page. Old links such as /#listings, /#tracker or
  // /?product=x#tracker can't be redirected by the server (the part after # never reaches it), so forward them here.
  // #sold-out-everywhere used to be a block on the tracker. That list now lives on its own page.
  const here = location.pathname;
  if (location.hash === "#sold-out-everywhere" && here !== "/sold-out-everywhere/" && here !== "/sold-out-everywhere/index.html") {
    location.replace("/sold-out-everywhere/" + location.search);
  } else if (here === "/" || here === "/index.html") {
    const moved = { tracker: "tracker", listings: "tracker", "by-product": "by-product", rows: "tracker" };
    const h = location.hash.slice(1), q = new URLSearchParams(location.search);
    const filt = ["product", "type", "store", "status", "q", "country"].some(k => q.get(k));
    // Old /#faq and /faq land on this page's Good to know, not the Hobonichi tracker.
    if (h === "faq" && !filt) location.replace("/#good-to-know" + location.search);
    else if (moved[h] || filt) location.replace("/hobonichi-restock-tracker/" + location.search + (moved[h] ? "#" + moved[h] : (h ? "#" + h : "#tracker")));
  }
  const statusBadge = st => st === "link_only"
    ? `<span class="lo-wrap"><a class="more-info" href="/transparency/" aria-label="More information about link-only listings (Transparency page)">More Information</a><span class="badge link_only">Link only</span></span>`
    : `<span class="badge ${esc(st)}">${LABEL[st] || esc(st)}</span>`;
  const LABEL = { in_stock: "In stock", preorder: "Preorder", coming_soon: "Not yet on sale", sold_out: "Sold out", unknown: "Couldn't check", link_only: "Link only" };

  const groupSel = "details.fam-block, details.group-fold";
  function bindGroupToggle(btn, root) {
    if (!btn) return () => {};
    const scope = root || document;
    const sync = () => {
      const items = [...scope.querySelectorAll(groupSel)].filter(d => !d.hidden);
      if (!items.length) { btn.hidden = true; return; }
      btn.hidden = false;
      const allOpen = items.every(d => d.open);
      btn.textContent = allOpen ? "Collapse all" : "Expand all";
      btn.setAttribute("aria-pressed", allOpen ? "true" : "false");
    };
    if (!btn.dataset.bound) {
      btn.dataset.bound = "1";
      btn.addEventListener("click", () => {
        const items = [...scope.querySelectorAll(groupSel)].filter(d => !d.hidden);
        const open = !items.every(d => d.open);
        items.forEach(d => { d.open = open; });
        sync();
      });
      scope.addEventListener("toggle", ev => {
        if (ev.target.closest && ev.target.matches && ev.target.matches(groupSel)) sync();
      }, true);
    }
    sync();
    return sync;
  }
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dataEl = document.getElementById("stock-data");
  if (dataEl) {
    // Rows come either as a plain list or packed ({k: keys, d: shared string tables, r: value rows}, see pack_rows in build_site.py).
    const rows = (() => {
      const raw = JSON.parse(dataEl.textContent);
      if (Array.isArray(raw)) return raw;
      return raw.r.map(vals => {
        const row = {};
        raw.k.forEach((k, i) => {
          const v = vals[i];
          if (v === null) return;
          row[k] = raw.d[k] ? raw.d[k][v] : v;
        });
        return row;
      });
    })();
    const order = { in_stock: 0, preorder: 1, coming_soon: 2, sold_out: 3, unknown: 4, link_only: 5 };
    rows.sort((a, b) => (order[a.st] - order[b.st]) || a.s.localeCompare(b.s));
    const $ = id => document.getElementById(id);
    const f = {};
    ["product", "type", "store", "status", "q", "size", "lang", "country"].forEach(k => {
      const el = $("f-" + k);
      if (el) f[k] = el;
    });
    const readParams = () => {
      const params = new URLSearchParams(location.search);
      for (const k in f) f[k].value = params.get(k) || "";
    };
    readParams();
    const PAGE = 15; let limit = PAGE;
    const more = document.getElementById("more");
    more.addEventListener("click", () => { limit += 1e9; render(); });
    let filterTimer = 0;
    const syncUrl = (push) => {
      const p = new URLSearchParams();
      for (const k in f) if (f[k].value) p.set(k, f[k].value);
      const next = location.pathname + (p.toString() ? "?" + p : "") + location.hash;
      if (next === location.pathname + location.search + location.hash) return;
      history[push ? "pushState" : "replaceState"](null, "", next);
    };
    // Filters work on listings; the table then groups the matching listings by product:
    // one header row per product (name, type, design page), then one row per shop with its status.
    function groupRows(out) {
      const groups = new Map();
      for (const r of out) {
        if (!groups.has(r.g)) groups.set(r.g, []);
        groups.get(r.g).push(r);
      }
      const best = ls => Math.min(...ls.map(r => order[r.st]));
      const nShops = ls => new Set(ls.map(r => r.sid)).size;
      return [...groups.values()].sort((a, b) => (best(a) - best(b)) || (nShops(b) - nShops(a)) || a[0].gn.localeCompare(b[0].gn));
    }
    function tally(all) {
      // Link-only listings are never counted as checked or in stock.
      const ls = all.filter(r => r.st !== "link_only");
      const n = ls.length;
      const unk = ls.filter(r => r.st === "unknown").length;
      const inn = ls.filter(r => r.st === "in_stock").length;
      if (!n) return all.length ? "Link only, we don't check stock" : "No listings";
      if (unk === n) return n === 1 ? "couldn't check this listing" : "couldn't check these " + n + " listings";
      if (unk) return inn + " of " + (n - unk) + " checked listings in stock · " + unk + " couldn't be checked";
      return inn + " of " + n + " listings in stock";
    }
    function shopTally(all) {
      const ls = all.filter(r => r.st !== "link_only");
      const links = new Set(all.filter(r => r.st === "link_only").map(r => r.sid)).size;
      if (!ls.length) return tally(all);
      const shops = new Set(ls.map(r => r.sid)).size;
      const inShops = new Set(ls.filter(r => r.st === "in_stock").map(r => r.sid)).size;
      return tally(ls) + " · " + inShops + " of " + shops + " " + (shops === 1 ? "shop" : "shops") + " in stock" + (links ? " · " + links + " " + (links === 1 ? "shop" : "shops") + " link only" : "");
    }
    function soldEverywhereNote(ls) {
      if (!ls.length || ls.some(r => r.st !== "sold_out")) return "";
      const n = new Set(ls.map(r => r.sid)).size;
      const text = n > 1 ? `Sold out at every shop we track (${n} shops).` : "Sold out at the only shop we track.";
      return `<p class="muted small">${text}</p>`;
    }
    function productCard(ls) {
      const h = ls[0];
      const anchor = h.c && /^[A-Za-z][\w-]*$/.test(h.c) ? ` id="${esc(h.c)}"` : "";
      const shops = new Set(ls.map(r => r.sid)).size;
      const bits = [esc(h.t), shops + " " + (shops === 1 ? "shop" : "shops")];
      if (h.dp) bits.push(`<a href="${esc(h.dp)}">Design page</a>`);
      const shopsHtml = ls.map(r => `<li><span class="compare-shop"><a href="${esc(r.u)}" target="_blank" rel="noopener">${esc(r.s)}</a>${r.rg ? ` <span class="region" title="Shop's home country">${esc(r.rg)}</span> ` : ""}${r.p && r.p !== r.gn ? `<span class="sub variant">${esc(r.p)}</span>` : ""}${r.title && r.title !== r.gn && r.title !== r.p ? `<span class="sub">${esc(r.title)}</span>` : ""}</span>${statusBadge(r.st)}${r.on && r.st === "sold_out" ? `<span class="official-note">${esc(r.on)}</span>` : ""}</li>`).join("");
      return `<article class="compare"${anchor}><header class="compare-head"><h3>${h.dp ? `<a href="${esc(h.dp)}">${esc(h.gn)}</a>` : esc(h.gn)}</h3><p class="compare-tally">${esc(shopTally(ls))}</p><p class="sub">${bits.join(" · ")}</p>${soldEverywhereNote(ls)}</header><ul class="compare-shops">${shopsHtml}</ul></article>`;
    }
    let honorHash = true;
    const filtersActive = () => Object.values(f).some(el => (el.value || "").trim() !== "");
    const hashId = () => {
      try { return decodeURIComponent((location.hash || "").slice(1)); }
      catch (e) { return ""; }
    };
    function openHashTarget(scroll) {
      const id = hashId();
      if (!id) return;
      const el = document.getElementById(id);
      if (!el) return;
      let node = el;
      while (node) {
        if (node.tagName === "DETAILS") node.open = true;
        node = node.parentElement;
      }
      if (scroll) revealHash(el);
    }
    function render() {
      const q = f.q.value.trim().toLowerCase();
      const out = rows.filter(r =>
        (!f.product.value || (f.product.value === "__other" ? !r.c : r.c === f.product.value)) &&
        (!f.type || !f.type.value || r.t === f.type.value) &&
        (!f.store.value || r.sid === f.store.value) &&
        (!f.status.value || r.st === f.status.value) &&
        (!f.size || !f.size.value || (r.sz || "") === f.size.value) &&
        (!f.lang || !f.lang.value || (r.lg || "") === f.lang.value) &&
        (!f.country || !f.country.value || (r.rg || "") === f.country.value) &&
        (!q || (r.p + " " + r.gn + " " + r.title + " " + r.s).toLowerCase().includes(q)));
      const groups = groupRows(out);
      const hasFam = groups.some(ls => ls[0].fam);
      if (hasFam && limit === PAGE) limit = 1e9;
      const shownGroups = []; let n = 0;
      for (const g of groups) { if (n >= limit) break; shownGroups.push(g); n += g.length; }
      more.hidden = n >= out.length;
      more.textContent = `Show all ${out.length} listings`;
      const box = $("rows");
      let html;
      if (!shownGroups.length) {
        html = box.tagName === "TBODY"
          ? `<tr class="empty-row"><td colspan="2">Nothing matches those filters.</td></tr>`
          : `<p class="empty-row">Nothing matches those filters.</p>`;
      } else if (!hasFam) {
        html = shownGroups.map(productCard).join("");
      } else {
        const fams = [];
        for (const g of shownGroups) {
          const key = g[0].fam || "";
          let bucket = fams.find(item => item.key === key);
          if (!bucket) {
            bucket = { key, name: g[0].famn || "Other", fo: g[0].fo == null ? 99 : g[0].fo, items: [] };
            fams.push(bucket);
          }
          bucket.items.push(g);
        }
        fams.sort((a, b) => a.fo - b.fo);
        const active = filtersActive();
        const linked = hashId();
        html = fams.map(fam => {
          const flat = fam.items.flat();
          const linkedHere = honorHash && linked && (linked === fam.key || fam.items.some(ls => ls.some(r => r.g === linked || r.c === linked)));
          const open = active || linkedHere ? " open" : "";
          const fid = /^[A-Za-z][\w-]*$/.test(fam.key) ? ` id="${esc(fam.key)}"` : "";
          return `<details class="fam-block"${fid}${open}><summary><span class="fam-name">${esc(fam.name)}</span><span class="fam-meta">${esc(tally(flat))}</span></summary><div class="fam-products">${fam.items.map(productCard).join("")}</div></details>`;
        }).join("");
      }
      box.innerHTML = html;
      if (honorHash) openHashTarget(false);
      $("count").textContent = `Showing ${n} of ${out.length} matching listings in ${groups.length} ${groups.length === 1 ? "product" : "products"} (${rows.filter(r => r.st !== "link_only").length} tracked${rows.some(r => r.st === "link_only") ? ", " + rows.filter(r => r.st === "link_only").length + " link only" : ""})`;
      const toggleBtn = document.querySelector("#tracker [data-group-toggle]") || document.querySelector("[data-group-toggle]");
      bindGroupToggle(toggleBtn, box.closest("#tracker") || document);
    }
    const reset = document.getElementById("f-reset");
    const onFilter = (push) => { limit = PAGE; render(); syncUrl(push); };
    Object.values(f).forEach(el => el.addEventListener("input", () => {
      clearTimeout(filterTimer);
      filterTimer = setTimeout(() => onFilter(el === f.q), el === f.q ? 250 : 0);
    }));
    if (reset) reset.addEventListener("click", () => {
      for (const k in f) f[k].value = "";
      honorHash = false;
      onFilter(true);
      honorHash = true;
    });
    window.addEventListener("popstate", () => { readParams(); limit = PAGE; render(); });
    render();
  }
  // Shop lists on family pages and design pages: search, store, and status, in place.
  const form = document.querySelector("form.page-filter");
  if (form) {
    const wrap = form.closest("#tracker") || form.closest("#stock") || form.parentElement;
    const cards = wrap.classList.contains("group-sec") ? [wrap] : [...wrap.querySelectorAll(".group-sec")];
    const heads = [...wrap.querySelectorAll(".shop-head")];
    const empty = wrap.querySelector(".card-empty");
    const qEl = form.querySelector("[data-filter=q]");
    const storeEl = form.querySelector("[data-filter=store]");
    const statusEl = form.querySelector("[data-filter=status]");
    const sizeEl = form.querySelector("[data-filter=size]");
    const langEl = form.querySelector("[data-filter=lang]");
    const countryEl = form.querySelector("[data-filter=country]");
    const reset = form.querySelector("[data-filter=reset]");
    const read = () => {
      const params = new URLSearchParams(location.search);
      if (qEl) qEl.value = params.get("q") || "";
      if (storeEl) storeEl.value = params.get("store") || "";
      if (statusEl) statusEl.value = params.get("status") || "";
      if (sizeEl) sizeEl.value = params.get("size") || "";
      if (langEl) langEl.value = params.get("lang") || "";
      if (countryEl) countryEl.value = params.get("country") || "";
    };
    const write = (push) => {
      const p = new URLSearchParams(location.search);
      const set = (k, v) => { if (v) p.set(k, v); else p.delete(k); };
      set("q", qEl && qEl.value.trim());
      set("store", storeEl && storeEl.value);
      set("status", statusEl && statusEl.value);
      set("size", sizeEl && sizeEl.value);
      set("lang", langEl && langEl.value);
      set("country", countryEl && countryEl.value);
      p.delete("product");
      const next = location.pathname + (p.toString() ? "?" + p : "") + location.hash;
      if (next !== location.pathname + location.search + location.hash)
        history[push ? "pushState" : "replaceState"](null, "", next);
    };
    let timer = 0;
    let skipHash = false;
    let hashScrolled = false;
    const openGroupHash = (scroll) => {
      const id = (() => { try { return decodeURIComponent((location.hash || "").slice(1)); } catch (e) { return ""; } })();
      if (!id) return;
      const el = document.getElementById(id);
      if (!el) return;
      let node = el;
      while (node) {
        if (node.tagName === "DETAILS") node.open = true;
        node = node.parentElement;
      }
      if (scroll) revealHash(el);
    };
    const filter = () => {
      const q = (qEl.value || "").trim().toLowerCase();
      const store = storeEl ? storeEl.value : "";
      const status = statusEl ? statusEl.value : "";
      const size = sizeEl ? sizeEl.value : "";
      const lang = langEl ? langEl.value : "";
      const country = countryEl ? countryEl.value : "";
      const active = !!(q || store || status || size || lang || country);
      let shown = 0;
      for (const c of cards) {
        let any = false;
        for (const tr of c.querySelectorAll("tbody tr")) {
          const head = c.closest("details.group-fold")?.querySelector("summary")?.textContent || c.querySelector("h2,h3")?.textContent || "";
          const text = (head + " " + tr.textContent).toLowerCase();
          const hit = (!q || text.includes(q)) && (!store || tr.getAttribute("data-store") === store) && (!status || tr.getAttribute("data-status") === status) && (!size || tr.getAttribute("data-size") === size) && (!lang || tr.getAttribute("data-lang") === lang) && (!country || tr.getAttribute("data-country") === country);
          tr.hidden = !hit; any = any || hit;
        }
        const keep = c.contains(form);
        c.hidden = !keep && active && !any;
        const fold = c.closest("details.group-fold");
        if (fold) {
          fold.hidden = c.hidden;
          if (active && any) fold.open = true;
          else if (!active) fold.open = false;
        }
        if (any) shown++;
      }
      for (const h of heads) {
        let el = h.nextElementSibling, vis = false;
        while (el && !el.classList.contains("shop-head")) {
          const sec = el.classList.contains("group-sec") ? el : el.querySelector && el.querySelector(".group-sec");
          if (sec && !sec.hidden && !el.hidden) vis = true;
          el = el.nextElementSibling;
        }
        h.hidden = !vis;
      }
      if (empty) empty.hidden = shown > 0;
      if (skipHash) skipHash = false;
      else { openGroupHash(!hashScrolled); hashScrolled = true; }
      const toggleBtn = form.parentElement && form.parentElement.querySelector("[data-group-toggle]");
      bindGroupToggle(toggleBtn, wrap);
    };
    const schedule = (push, wait) => {
      clearTimeout(timer);
      timer = setTimeout(() => { filter(); write(push); }, wait);
    };
    read();
    // Old dot-grid links pointed at a shop heading (#shop-archerolive). The list is grouped
    // by product now, so that hash opens the store filter instead of a missing heading.
    const shopHash = () => {
      const m = /^shop-([A-Za-z0-9_-]+)$/.exec((location.hash || "").slice(1));
      if (!m || !storeEl) return false;
      if (![...storeEl.options].some(o => o.value === m[1])) return false;
      storeEl.value = m[1];
      return true;
    };
    const fromShop = shopHash();
    if (qEl) qEl.addEventListener("input", () => schedule(true, 250));
    if (storeEl) storeEl.addEventListener("input", () => schedule(true, 0));
    if (statusEl) statusEl.addEventListener("input", () => schedule(true, 0));
    if (sizeEl) sizeEl.addEventListener("input", () => schedule(true, 0));
    if (langEl) langEl.addEventListener("input", () => schedule(true, 0));
    if (countryEl) countryEl.addEventListener("input", () => schedule(true, 0));
    if (reset) reset.addEventListener("click", () => {
      if (qEl) qEl.value = "";
      if (storeEl) storeEl.value = "";
      if (statusEl) statusEl.value = "";
      if (sizeEl) sizeEl.value = "";
      if (langEl) langEl.value = "";
      if (countryEl) countryEl.value = "";
      document.querySelectorAll("details.group-fold").forEach(d => { d.open = false; });
      skipHash = true;
      schedule(true, 0);
    });
    window.addEventListener("hashchange", () => {
      if (shopHash()) { filter(); const first = wrap.querySelector("details.group-fold:not([hidden])"); if (first) first.scrollIntoView({ block: "start" }); return; }
      openGroupHash(true);
    });
    window.addEventListener("popstate", () => { read(); shopHash(); filter(); });
    filter();
    if (fromShop) {
      const first = wrap.querySelector("details.group-fold:not([hidden])");
      if (first) first.scrollIntoView({ block: "start" });
    }
    const pid = new URLSearchParams(location.search).get("product");
    const target = pid && document.getElementById(pid);
    if (target) target.scrollIntoView();
  }
  // A #anchor inside a closed group (a guide section, a family, a product) opens that group.
  const openLinkedDetails = (scroll) => {
    const raw = (location.hash || "").slice(1);
    if (!raw) return;
    let id = raw;
    try { id = decodeURIComponent(raw); } catch (e) { return; }
    const el = document.getElementById(id);
    if (!el) return;
    let node = el;
    while (node) {
      if (node.tagName === "DETAILS") node.open = true;
      node = node.parentElement;
    }
    if (scroll) revealHash(el);
  };
  function revealHash(el) {
    const box = el.closest("details") || el;
    const go = () => box.scrollIntoView({ block: "start" });
    go();
    requestAnimationFrame(go);
  }
  window.addEventListener("hashchange", () => openLinkedDetails(true));
  openLinkedDetails(true);
  // Stock tables sit in a horizontal scroller, so a CSS sticky header sticks to that
  // box and slides under the site header. Keep the header row just below the site header.
  const pinTableHeads = () => {
    const mastEl = document.querySelector(".masthead");
    if (!mastEl) return;
    const mast = mastEl.getBoundingClientRect().bottom;
    document.querySelectorAll("table.stock thead").forEach(thead => {
      const cells = [...thead.querySelectorAll("th")];
      cells.forEach(th => { th.style.transform = ""; });
      const wrap = thead.closest(".table-wrap") || thead.parentElement;
      const wr = wrap.getBoundingClientRect();
      const hr = thead.getBoundingClientRect();
      const room = wr.bottom - hr.height;
      let shift = 0;
      if (hr.top < mast && room > mast) shift = Math.min(mast - hr.top, Math.max(0, room - hr.top));
      if (shift) cells.forEach(th => { th.style.transform = "translateY(" + shift + "px)"; });
    });
  };
  window.addEventListener("scroll", pinTableHeads, { passive: true });
  window.addEventListener("resize", pinTableHeads);
  pinTableHeads();
  // Restock-alert signup: Cloudflare Turnstile (anti-spam) + our own /api/subscribe. Without JavaScript the form still
  // posts to /api/subscribe and gets a plain result page (which says the anti-spam check needs JavaScript).
  const signupForms = document.querySelectorAll("form[data-turnstile]");
  if (signupForms.length) {
    const ts = document.createElement("script");
    ts.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
    ts.async = true; ts.defer = true;
    document.head.appendChild(ts);
    signupForms.forEach(form => {
      const status = form.querySelector(".signup-status");
      const btn = form.querySelector("button[type=submit]");
      const say = (msg, ok) => { status.textContent = msg; status.hidden = false; status.dataset.state = ok ? "ok" : "error"; };
      const tokenOf = () => (form.querySelector("[name=cf-turnstile-response]") || {}).value || "";
      form.addEventListener("submit", async e => {
        e.preventDefault();
        if (btn.disabled) return;
        if (![...form.querySelectorAll("input[name='tags[]']")].some(c => c.checked)) { say("Pick at least one tracker so we know what to email you about.", false); return; }
        btn.disabled = true; status.hidden = true;
        for (let i = 0; i < 40 && !tokenOf(); i++) await new Promise(r => setTimeout(r, 250));
        try {
          const res = await fetch(form.action, { method: "POST", body: new FormData(form), headers: { Accept: "application/json" } });
          const data = await res.json().catch(() => ({}));
          say(data.message || "Something went wrong. Please try again.", !!data.ok);
          if (data.ok) form.querySelector("input[type=email]").value = "";
        } catch (_) { say("We couldn't reach the server. Please try again.", false); }
        if (window.turnstile) { try { window.turnstile.reset(); } catch (_) {} }
        btn.disabled = false;
      });
    });
  }
  // A shop link from homepage search lands on the ink tracker with ?store=. Hide the other inks.
  const inkNote = document.getElementById("ink-store-note");
  if (inkNote) {
    const sid = new URLSearchParams(location.search).get("store");
    if (sid) {
      const tracker = inkNote.closest("#tracker") || document;
      let shown = 0;
      tracker.querySelectorAll("details.group-fold").forEach(card => {
        const hit = (card.getAttribute("data-stores") || "").split(/\s+/).includes(sid);
        card.hidden = !hit;
        if (hit) { card.open = true; shown += 1; }
      });
      tracker.querySelectorAll("h2.shop-head").forEach(head => {
        let el = head.nextElementSibling, vis = false;
        while (el && !(el.classList && el.classList.contains("shop-head"))) {
          if (el.matches && el.matches("details.group-fold") && !el.hidden) vis = true;
          el = el.nextElementSibling;
        }
        head.hidden = !vis;
      });
      inkNote.hidden = false;
      inkNote.textContent = shown ? "Showing inks this shop lists." : "This shop has no ink on the tracker.";
    }
  }
  // find-item: homepage search. The index is fetched only from focus or input, never on load.
  const findInput = document.getElementById("find-q");
  if (findInput) {
    const findForm = document.getElementById("find-form");
    const findList = document.getElementById("find-list");
    const findCount = document.getElementById("find-count");
    let findData = null;
    let findIndexP = null;
    let active = -1;
    const fold = s => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    const loadFindIndex = () => {
      if (!findIndexP) {
        findIndexP = fetch("/data/search-index.json").then(r => {
          if (!r.ok) throw new Error("search index");
          return r.json();
        }).then(data => { findData = data; return data; });
      }
      return findIndexP;
    };
    const say = msg => { if (findCount.textContent !== msg) findCount.textContent = msg; };
    const fail = () => { if (findInput.value.trim()) say("The item list didn't load. Search still opens the Hobonichi tracker."); };
    const options = () => [...findList.querySelectorAll('[role="option"]')];
    const closeList = () => {
      findList.hidden = true;
      findInput.setAttribute("aria-expanded", "false");
      findInput.removeAttribute("aria-activedescendant");
      active = -1;
      options().forEach(el => el.setAttribute("aria-selected", "false"));
    };
    const setActive = i => {
      const opts = options();
      if (!opts.length) return;
      if (i < 0) i = opts.length - 1;
      if (i >= opts.length) i = 0;
      opts.forEach((el, n) => el.setAttribute("aria-selected", n === i ? "true" : "false"));
      active = i;
      findInput.setAttribute("aria-activedescendant", opts[i].id);
      if (opts[i].scrollIntoView) opts[i].scrollIntoView({ block: "nearest" });
    };
    const activeLink = () => {
      if (active < 0 || findList.hidden) return "";
      const el = document.getElementById("find-opt-" + active);
      return el ? el.href : "";
    };
    const tokensOf = q => fold(q).split(/[^a-z0-9]+/).filter(Boolean);
    const hayOf = item => fold([item.n, item.q || "", (item.sh || []).map(i => findData.shops[i].n).join(" "), findData.trackers[item.t].l].join(" "));
    const generalUrl = raw => {
      if (!findData) return "";
      const query = fold(raw.trim());
      const tokens = tokensOf(raw);
      if (query.length < 2 || !tokens.length) return "";
      const shops = findData.shops.filter(shop => fold(shop.n).includes(query) && tokens.every(t => fold(shop.n).includes(t)));
      if (shops.length === 1 && shops[0].p.length) {
        const rank = { h: 0, d: 1, i: 2 };
        const pages = shops[0].p.slice().sort((a, b) => (b.c - a.c) || (rank[a.t] - rank[b.t]));
        return pages[0].u;
      }
      const hits = findData.items.filter(item => tokens.every(t => hayOf(item).includes(t)));
      if (!hits.length) return "";
      const counts = {};
      hits.forEach(item => { counts[item.t] = (counts[item.t] || 0) + 1; });
      const best = Object.keys(counts).sort((a, b) => counts[b] - counts[a] || (a === "h" ? -1 : 1))[0];
      if (best === "i") return hits.find(item => item.t === "i").u;
      return findData.trackers[best].u + "?q=" + encodeURIComponent(raw.trim());
    };
    const render = () => {
      if (!findData) return;
      const raw = findInput.value.trim();
      const query = fold(raw);
      const tokens = tokensOf(raw);
      findList.replaceChildren();
      active = -1;
      findInput.removeAttribute("aria-activedescendant");
      if (query.length < 2 || !tokens.length) { closeList(); say(""); return; }
      const shopRows = [];
      findData.shops.forEach(shop => {
        const name = fold(shop.n);
        if (!tokens.every(t => name.includes(t))) return;
        shop.p.forEach(page => shopRows.push({ n: shop.n, t: page.t, s: page.s, u: page.u }));
      });
      const rank = { h: 0, d: 1, i: 2 };
      shopRows.sort((a, b) => (fold(a.n).startsWith(query) ? 0 : 1) - (fold(b.n).startsWith(query) ? 0 : 1)
        || fold(a.n).localeCompare(fold(b.n)) || (rank[a.t] - rank[b.t]));
      const itemRows = findData.items.map(item => {
        const name = fold(item.n);
        const hay = hayOf(item);
        if (!tokens.every(t => hay.includes(t))) return null;
        let score = 30;
        if (name === query) score = 100;
        else if (name.startsWith(query)) score = 80;
        else if (tokens.every(t => name.includes(t))) score = 60;
        return { n: item.n, t: item.t, s: item.s, u: item.u, score };
      }).filter(Boolean).sort((a, b) => b.score - a.score || a.n.localeCompare(b.n));
      const rows = shopRows.slice(0, 3).concat(itemRows.slice(0, Math.max(0, 8 - Math.min(shopRows.length, 3))));
      if (!rows.length) { closeList(); say("No matches"); return; }
      rows.forEach((row, i) => {
        const link = document.createElement("a");
        link.href = row.u;
        link.id = "find-opt-" + i;
        link.setAttribute("role", "option");
        link.setAttribute("aria-selected", "false");
        const name = document.createElement("span");
        name.className = "find-name";
        name.textContent = row.n;
        const tag = document.createElement("span");
        tag.className = "find-tag";
        tag.textContent = findData.trackers[row.t].l;
        const sum = document.createElement("span");
        sum.className = "find-sum";
        sum.textContent = row.s;
        link.append(name, tag, sum);
        findList.append(link);
      });
      findList.hidden = false;
      findInput.setAttribute("aria-expanded", "true");
      say(rows.length === 1 ? "1 match" : rows.length + " matches");
    };
    findInput.addEventListener("focus", () => { loadFindIndex().then(render).catch(fail); });
    findInput.addEventListener("input", () => { loadFindIndex().then(render).catch(fail); });
    findInput.addEventListener("keydown", e => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (findList.hidden || !options().length) return;
        e.preventDefault();
        setActive(active + (e.key === "ArrowDown" ? 1 : -1));
      } else if (e.key === "Escape") {
        if (!findList.hidden) { e.preventDefault(); closeList(); }
        else if (findInput.value) { findInput.value = ""; say(""); }
      } else if (e.key === "Enter" && activeLink()) {
        e.preventDefault();
        location.href = activeLink();
      }
    });
    findList.addEventListener("pointerover", e => {
      const opt = e.target.closest && e.target.closest('[role="option"]');
      if (!opt || !findList.contains(opt)) return;
      const n = Number(opt.id.slice("find-opt-".length));
      if (!Number.isNaN(n)) setActive(n);
    });
    findForm.addEventListener("submit", e => {
      const picked = activeLink();
      if (picked) { e.preventDefault(); location.href = picked; return; }
      if (!findIndexP) return;
      e.preventDefault();
      const raw = findInput.value;
      findIndexP.then(() => {
        location.href = generalUrl(raw) || findForm.action + (raw.trim() ? "?q=" + encodeURIComponent(raw.trim()) : "");
      }).catch(() => {
        location.href = findForm.action + (raw.trim() ? "?q=" + encodeURIComponent(raw.trim()) : "");
      });
    });
    document.addEventListener("pointerdown", e => { if (!findForm.contains(e.target)) closeList(); });
    document.addEventListener("keydown", e => {
      const typing = e.target && e.target.closest && e.target.closest("input, textarea, select, [contenteditable='true']");
      if (typing) return;
      const slash = e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey;
      const palette = (e.metaKey || e.ctrlKey) && !e.altKey && (e.key === "k" || e.key === "K");
      if (!slash && !palette) return;
      e.preventDefault();
      findInput.focus();
    });
  }
})();
