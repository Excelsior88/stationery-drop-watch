// Stationery Drop Watch: client-side table filtering. The check time is shown once per table (build_site.py).
(function () {
  if (window.DropWatchTime) window.DropWatchTime.showLocalTimes(document);
  // The Hobonichi tracker moved from the homepage to its own page. Old links such as /#listings, /#tracker or
  // /?product=x#tracker can't be redirected by the server (the part after # never reaches it), so forward them here.
  if (location.pathname === "/" || location.pathname === "/index.html") {
    const moved = { tracker: "tracker", listings: "tracker", "by-product": "by-product", "sold-out-everywhere": "sold-out-everywhere", faq: "faq", rows: "tracker" };
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
    const f = { product: $("f-product"), type: $("f-type"), store: $("f-store"), status: $("f-status"), q: $("f-q") };
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
    function render() {
      const q = f.q.value.trim().toLowerCase();
      const out = rows.filter(r =>
        (!f.product.value || (f.product.value === "__other" ? !r.c : r.c === f.product.value)) &&
        (!f.type.value || r.t === f.type.value) &&
        (!f.store.value || r.sid === f.store.value) &&
        (!f.status.value || r.st === f.status.value) &&
        (!q || (r.p + " " + r.gn + " " + r.title + " " + r.s).toLowerCase().includes(q)));
      const groups = groupRows(out);
      const shownGroups = []; let n = 0;
      for (const g of groups) { if (n >= limit) break; shownGroups.push(g); n += g.length; }
      more.hidden = n >= out.length;
      more.textContent = `Show all ${out.length} listings`;
      $("rows").innerHTML = shownGroups.length ? shownGroups.map(ls => {
        const h = ls[0];
        const sameAz = ls.every(r => r.az === h.az && !!r.azm === !!h.azm);
        const shops = new Set(ls.map(r => r.sid)).size;
        return `<tr class="grp"><th colspan="2" scope="rowgroup"><div class="grp-head">
          <span class="grp-name">${h.dp ? `<a href="${esc(h.dp)}">${esc(h.gn)}</a>` : esc(h.gn)}</span>
          <span class="sub">${esc(h.t)} · ${shops} ${shops === 1 ? "shop" : "shops"}${h.dp ? ` · <a href="${esc(h.dp)}">Design page</a>` : ""}</span>
          ${h.az && sameAz ? azLink(h, "grp-az") : ""}</div></th></tr>` +
          ls.map(r => `<tr class="child">
          <td><a href="${esc(r.u)}" target="_blank" rel="noopener">${esc(r.s)}</a>${r.rg ? ` <span class="region" title="Shop's home country">${esc(r.rg)}</span>` : ""}<span class="sub variant">${esc(r.p)}</span>${r.title && r.title !== r.gn && r.title !== r.p ? `<span class="sub">${esc(r.title)}</span>` : ""}${r.az && !sameAz ? `<span class="sub">${azLink(r)}</span>` : ""}</td>
          <td><span class="badge ${esc(r.st)}">${LABEL[r.st] || esc(r.st)}</span></td>
        </tr>`).join("");
      }).join("") : `<tr class="empty-row"><td colspan="2">Nothing matches those filters.</td></tr>`;
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
      onFilter(true);
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
    const reset = form.querySelector("[data-filter=reset]");
    const read = () => {
      const params = new URLSearchParams(location.search);
      if (qEl) qEl.value = params.get("q") || "";
      if (storeEl) storeEl.value = params.get("store") || "";
      if (statusEl) statusEl.value = params.get("status") || "";
    };
    const write = (push) => {
      const p = new URLSearchParams(location.search);
      const set = (k, v) => { if (v) p.set(k, v); else p.delete(k); };
      set("q", qEl && qEl.value.trim());
      set("store", storeEl && storeEl.value);
      set("status", statusEl && statusEl.value);
      p.delete("product");
      const next = location.pathname + (p.toString() ? "?" + p : "") + location.hash;
      if (next !== location.pathname + location.search + location.hash)
        history[push ? "pushState" : "replaceState"](null, "", next);
    };
    let timer = 0;
    const filter = () => {
      const q = (qEl.value || "").trim().toLowerCase();
      const store = storeEl ? storeEl.value : "";
      const status = statusEl ? statusEl.value : "";
      let shown = 0;
      for (const c of cards) {
        let any = false;
        for (const tr of c.querySelectorAll("tbody tr")) {
          const text = ((c.querySelector("h2,h3")?.textContent || "") + " " + tr.textContent).toLowerCase();
          const hit = (!q || text.includes(q)) && (!store || tr.getAttribute("data-store") === store) && (!status || tr.getAttribute("data-status") === status);
          tr.hidden = !hit; any = any || hit;
        }
        const keep = c.contains(form);
        c.hidden = !keep && (q || store || status) && !any;
        if (any) shown++;
      }
      for (const h of heads) {
        let el = h.nextElementSibling, vis = false;
        while (el && !el.classList.contains("shop-head")) { if (el.classList.contains("group-sec") && !el.hidden) vis = true; el = el.nextElementSibling; }
        h.hidden = !vis;
      }
      if (empty) empty.hidden = shown > 0;
    };
    const schedule = (push, wait) => {
      clearTimeout(timer);
      timer = setTimeout(() => { filter(); write(push); }, wait);
    };
    read();
    if (qEl) qEl.addEventListener("input", () => schedule(true, 250));
    if (storeEl) storeEl.addEventListener("input", () => schedule(true, 0));
    if (statusEl) statusEl.addEventListener("input", () => schedule(true, 0));
    if (reset) reset.addEventListener("click", () => {
      if (qEl) qEl.value = "";
      if (storeEl) storeEl.value = "";
      if (statusEl) statusEl.value = "";
      schedule(true, 0);
    });
    window.addEventListener("popstate", () => { read(); filter(); });
    filter();
    const pid = new URLSearchParams(location.search).get("product");
    const target = pid && document.getElementById(pid);
    if (target) target.scrollIntoView();
  }
})();
