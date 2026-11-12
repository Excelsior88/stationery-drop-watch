// Stationery Drop Watch: client-side table filtering. The check time is shown once per table (build_site.py).
(function () {
  if (window.DropWatchTime) window.DropWatchTime.showLocalTimes(document);
  document.querySelectorAll("details.feed-fold").forEach(d => { d.open = false; });
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
    const moved = { tracker: "tracker", listings: "tracker", "by-product": "by-product", faq: "faq", rows: "tracker" };
    const h = location.hash.slice(1), q = new URLSearchParams(location.search);
    const filt = ["product", "type", "store", "status", "q"].some(k => q.get(k));
    if (moved[h] || filt) location.replace("/hobonichi-restock-tracker/" + location.search + (moved[h] ? "#" + moved[h] : (h ? "#" + h : "#tracker")));
  }
  const LABEL = { in_stock: "In stock", preorder: "Preorder", coming_soon: "Not yet on sale", sold_out: "Sold out", unknown: "Couldn't check" };
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dataEl = document.getElementById("stock-data");
  if (dataEl) {
    const rows = JSON.parse(dataEl.textContent);
    const order = { in_stock: 0, preorder: 1, coming_soon: 2, sold_out: 3, unknown: 4 };
    rows.sort((a, b) => (order[a.st] - order[b.st]) || a.s.localeCompare(b.s));
    const $ = id => document.getElementById(id);
    const f = {};
    ["product", "type", "store", "status", "q", "size", "lang"].forEach(k => {
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
    // one header row per product (name, type, design page, Amazon link), then one row per shop with its status.
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
    const azLink = (r, cls) => r.azm
      ? `<a class="btn btn-amz btn-sm" href="${esc(r.az)}" target="_blank" rel="sponsored noopener">${esc(r.azl)}</a>`
      : `<a class="az${cls ? " " + cls : ""}" href="${esc(r.az)}" target="_blank" rel="sponsored noopener">${esc(r.azl)}</a>`;
    function tally(ls) {
      const n = ls.length;
      const unk = ls.filter(r => r.st === "unknown").length;
      const inn = ls.filter(r => r.st === "in_stock").length;
      if (!n) return "No listings";
      if (unk === n) return n === 1 ? "couldn't check this listing" : "couldn't check these " + n + " listings";
      if (unk) return inn + " of " + (n - unk) + " checked listings in stock · " + unk + " couldn't be checked";
      return inn + " of " + n + " listings in stock";
    }
    function shopTally(ls) {
      const shops = new Set(ls.map(r => r.sid)).size;
      const inShops = new Set(ls.filter(r => r.st === "in_stock").map(r => r.sid)).size;
      return tally(ls) + " · " + inShops + " of " + shops + " " + (shops === 1 ? "shop" : "shops") + " in stock";
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
      const sameAz = ls.every(r => r.az === h.az && !!r.azm === !!h.azm);
      const shops = new Set(ls.map(r => r.sid)).size;
      const bits = [esc(h.t), shops + " " + (shops === 1 ? "shop" : "shops")];
      if (h.dp) bits.push(`<a href="${esc(h.dp)}">Design page</a>`);
      const shopsHtml = ls.map(r => `<li><span class="compare-shop"><a href="${esc(r.u)}" target="_blank" rel="noopener">${esc(r.s)}</a>${r.rg ? ` <span class="region" title="Shop's home country">${esc(r.rg)}</span>` : ""}${r.p && r.p !== r.gn ? `<span class="sub variant">${esc(r.p)}</span>` : ""}${r.title && r.title !== r.gn && r.title !== r.p ? `<span class="sub">${esc(r.title)}</span>` : ""}${r.az && !sameAz ? azLink(r) : ""}</span><span class="badge ${esc(r.st)}">${LABEL[r.st] || esc(r.st)}</span></li>`).join("");
      return `<article class="compare"${anchor}><header class="compare-head"><h3>${h.dp ? `<a href="${esc(h.dp)}">${esc(h.gn)}</a>` : esc(h.gn)}</h3><p class="compare-tally">${esc(shopTally(ls))}</p><p class="sub">${bits.join(" · ")}</p>${h.az && sameAz ? azLink(h, "grp-az") : ""}${soldEverywhereNote(ls)}</header><ul class="compare-shops">${shopsHtml}</ul></article>`;
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
      $("count").textContent = `Showing ${n} of ${out.length} matching listings in ${groups.length} ${groups.length === 1 ? "product" : "products"} (${rows.length} tracked)`;
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
    const reset = form.querySelector("[data-filter=reset]");
    const read = () => {
      const params = new URLSearchParams(location.search);
      if (qEl) qEl.value = params.get("q") || "";
      if (storeEl) storeEl.value = params.get("store") || "";
      if (statusEl) statusEl.value = params.get("status") || "";
      if (sizeEl) sizeEl.value = params.get("size") || "";
      if (langEl) langEl.value = params.get("lang") || "";
    };
    const write = (push) => {
      const p = new URLSearchParams(location.search);
      const set = (k, v) => { if (v) p.set(k, v); else p.delete(k); };
      set("q", qEl && qEl.value.trim());
      set("store", storeEl && storeEl.value);
      set("status", statusEl && statusEl.value);
      set("size", sizeEl && sizeEl.value);
      set("lang", langEl && langEl.value);
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
      let shown = 0;
      for (const c of cards) {
        let any = false;
        for (const tr of c.querySelectorAll("tbody tr")) {
          const head = c.closest("details.group-fold")?.querySelector("summary")?.textContent || c.querySelector("h2,h3")?.textContent || "";
          const text = (head + " " + tr.textContent).toLowerCase();
          const hit = (!q || text.includes(q)) && (!store || tr.getAttribute("data-store") === store) && (!status || tr.getAttribute("data-status") === status) && (!size || tr.getAttribute("data-size") === size) && (!lang || tr.getAttribute("data-lang") === lang);
          tr.hidden = !hit; any = any || hit;
        }
        const keep = c.contains(form);
        c.hidden = !keep && (q || store || status) && !any;
        const fold = c.closest("details.group-fold");
        if (fold) {
          fold.hidden = c.hidden;
          if ((q || store || status || size || lang) && any) fold.open = true;
          else if (!(q || store || status || size || lang)) fold.open = false;
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
    if (reset) reset.addEventListener("click", () => {
      if (qEl) qEl.value = "";
      if (storeEl) storeEl.value = "";
      if (statusEl) statusEl.value = "";
      if (sizeEl) sizeEl.value = "";
      if (langEl) langEl.value = "";
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
})();
