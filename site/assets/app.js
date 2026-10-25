// Stationery Drop Watch: client-side table filtering.
(function () {
  const LABEL = { in_stock: "In stock", preorder: "Preorder", coming_soon: "Not yet on sale", sold_out: "Sold out", unknown: "Couldn't check" };
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function ago(iso) {
    const m = Math.round((Date.now() - new Date(iso)) / 60000);
    if (m < 1) return "just now"; if (m < 60) return m + " min ago";
    const h = Math.round(m / 60); if (h < 48) return h + " h ago";
    return Math.round(h / 24) + " days ago";
  }
  const dataEl = document.getElementById("stock-data");
  if (dataEl) {
    const rows = JSON.parse(dataEl.textContent);
    const order = { in_stock: 0, preorder: 1, coming_soon: 2, sold_out: 3, unknown: 4 };
    rows.sort((a, b) => (order[a.st] - order[b.st]) || a.p.localeCompare(b.p) || a.s.localeCompare(b.s));
    const $ = id => document.getElementById(id);
    const f = { product: $("f-product"), type: $("f-type"), store: $("f-store"), status: $("f-status"), q: $("f-q") };
    const params = new URLSearchParams(location.search);
    for (const k in f) if (params.get(k)) f[k].value = params.get(k);
    const PAGE = 15; let limit = PAGE;
    const more = document.getElementById("more");
    more.addEventListener("click", () => { limit += 1e9; render(); });
    function render() {
      const q = f.q.value.trim().toLowerCase();
      const out = rows.filter(r =>
        (!f.product.value || (f.product.value === "__other" ? !r.c : r.c === f.product.value)) &&
        (!f.type.value || r.t === f.type.value) &&
        (!f.store.value || r.sid === f.store.value) &&
        (!f.status.value || r.st === f.status.value) &&
        (!q || (r.p + " " + r.title + " " + r.s).toLowerCase().includes(q)));
      const shown = out.slice(0, limit);
      more.hidden = out.length <= limit;
      more.textContent = `Show all ${out.length} listings`;
      $("rows").innerHTML = shown.length ? shown.map(r => `<tr>
        <td><a href="${esc(r.u)}" target="_blank" rel="noopener">${esc(r.p)}</a><span class="sub">${esc(r.t)}${r.az && !r.azm ? ` · <a class="az" href="${esc(r.az)}" target="_blank" rel="sponsored noopener">${esc(r.azl)}</a>` : ""}</span>${r.azm ? `<a class="btn btn-amz btn-sm" href="${esc(r.az)}" target="_blank" rel="sponsored noopener">${esc(r.azl)}</a>` : ""}</td>
        <td>${esc(r.s)}</td>
        <td><span class="badge ${esc(r.st)}">${LABEL[r.st] || esc(r.st)}</span></td>
        <td class="hide-sm"><time datetime="${esc(r.at)}" title="${esc(new Date(r.at).toLocaleString())}">${ago(r.at)}</time></td>
      </tr>`).join("") : `<tr class="empty-row"><td colspan="4">Nothing matches those filters.</td></tr>`;
      $("count").textContent = `Showing ${shown.length} of ${out.length} matching (${rows.length} tracked)`;
    }
    Object.values(f).forEach(el => el.addEventListener("input", () => { limit = PAGE; render(); }));
    render();
  }
})();
