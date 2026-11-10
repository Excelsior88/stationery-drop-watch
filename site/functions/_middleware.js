// Cloudflare Pages serves 404.html with HTTP 404 for unknown paths, and also
// serves that same file at /404 (and redirects /404.html there) with HTTP 200.
// Pages _redirects cannot set a 404 status. This middleware makes those URLs a real 404.
const NOT_FOUND = new Set(["/404", "/404/", "/404.html"]);

export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (!NOT_FOUND.has(url.pathname)) return context.next();
  const assetUrl = new URL(context.request.url);
  assetUrl.pathname = "/404.html";
  const asset = await context.env.ASSETS.fetch(new Request(assetUrl.toString(), { method: "GET" }));
  const headers = new Headers(asset.headers);
  headers.set("content-type", "text/html; charset=utf-8");
  headers.set("x-robots-tag", "noindex");
  return new Response(asset.body, { status: 404, headers });
}
