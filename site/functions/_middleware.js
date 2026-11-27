// Cloudflare Pages serves 404.html with HTTP 404 for unknown paths, and also
// serves that same file at /404 (and redirects /404.html there) with HTTP 200.
// Pages _redirects cannot set a 404 or 410 status. This middleware makes those URLs a real 404,
// and answers the retired Traveler's Company and MIDORI pages with 410 Gone.
const NOT_FOUND = new Set(["/404", "/404/", "/404.html"]);
// Keep in sync with GONE_PATHS in scripts/build_site.py (tests/test_gone_pages.py checks this list).
const GONE = [
  "travelers-company-limited-edition/regular-black",
  "travelers-company-limited-edition/regular-blue",
  "travelers-company-limited-edition/regular-brown",
  "travelers-company-limited-edition/regular-camel",
  "travelers-company-limited-edition/regular-olive",
  "travelers-company-limited-edition/road-trip-brown",
  "travelers-company-limited-edition/card-size-20th-anniversary-black",
  "midori-md-limited-edition/md-diary-2027-a5",
  "midori-md-limited-edition/md-diary-1-day-1-page-2027-a5",
  "travelers-notebook-regular-size",
  "travelers-notebook-regular-vs-passport-vs-card-size",
];
const GONE_PATHS = new Set(GONE.flatMap(p => ["/" + p, "/" + p + "/", "/" + p + "/index.html"]));

async function notFoundPage(context, status) {
  const assetUrl = new URL(context.request.url);
  assetUrl.pathname = "/404.html";
  const asset = await context.env.ASSETS.fetch(new Request(assetUrl.toString(), { method: "GET" }));
  const headers = new Headers(asset.headers);
  headers.set("content-type", "text/html; charset=utf-8");
  headers.set("x-robots-tag", "noindex");
  return new Response(asset.body, { status, headers });
}

export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (NOT_FOUND.has(url.pathname)) return notFoundPage(context, 404);
  if (GONE_PATHS.has(url.pathname)) return notFoundPage(context, 410);
  return context.next();
}
