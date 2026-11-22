// POST /api/subscribe: restock-alert signup.
// Flow: honeypot -> same-origin check -> email + tag validation -> Cloudflare Turnstile siteverify -> Kit API v4.
// Kit: create the subscriber as "inactive", add it to the double opt-in form (this is the call that makes Kit send its
// confirmation email), then apply the chosen tag ids. Tags can be applied before confirmation (checked Nov 22, 2026).
// Secrets (Pages environment secrets, never committed): KIT_API_KEY, TURNSTILE_SECRET.
const KIT_API = "https://api.kit.com/v4";
const KIT_FORM_ID = "10225471";
const TAGS = { "26280763": "Hobonichi", "26280764": "Dot grid journals", "26280765": "Limited-edition inks" };
const SITEVERIFY = "https://challenges.cloudflare.com/turnstile/v0/siteverify";
const EMAIL_RE = /^[^\s@<>()[\]\\,;:"]+@[^\s@<>()[\]\\,;:"]+\.[^\s@<>()[\]\\,;:"]{2,}$/;
const KIT_HOSTED_FORM = "https://stationery-drop-watch.kit.com/ada05fa216";

const MSG = {
  ok: "Almost done. Check your inbox for a confirmation email from Stationery Drop Watch and click the link in it. You aren't on the list until you click it. If you are already on the list, nothing changes: use the \"Update your profile\" link in any of our emails to change what you get.",
  email: "That email address doesn't look right. Please check it and try again.",
  tags: "Pick at least one tracker so we know what to email you about.",
  check: "The anti-spam check didn't pass. Please reload the page and try again. It needs JavaScript and a browser that can run Cloudflare Turnstile.",
  origin: "That request didn't come from our site.",
  upstream: "We couldn't add you just now. Please try again in a few minutes.",
  method: "Use the signup form on the site.",
};

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function wantsJson(request) {
  const a = request.headers.get("accept") || "";
  return a.includes("application/json") || new URL(request.url).searchParams.get("json") === "1";
}

function reply(request, status, ok, message, extra = {}) {
  const headers = { "cache-control": "no-store", "x-robots-tag": "noindex" };
  if (wantsJson(request)) {
    return new Response(JSON.stringify({ ok, message, ...extra }), { status, headers: { ...headers, "content-type": "application/json; charset=utf-8" } });
  }
  const fallback = ok ? "" : `<p>If this keeps happening you can also sign up on <a href="${KIT_HOSTED_FORM}">our Kit signup page</a>, or email us at <a href="mailto:admin@stationerydropwatch.com">admin@stationerydropwatch.com</a>.</p>`;
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>${ok ? "Check your email" : "Signup problem"} | Stationery Drop Watch</title>
<style>body{margin:0;background:#fbf6ec;color:#2a2420;font:17px/1.55 Georgia,"Times New Roman",serif}main{max-width:560px;margin:12vh auto;padding:0 20px}h1{font-size:1.7rem;margin:0 0 .4em}a{color:#a8452e}.brand{font-size:1rem;margin-bottom:1.5rem}.btn{display:inline-block;margin-top:.8rem;padding:.55em 1.1em;background:#a8452e;color:#fff;border-radius:8px;text-decoration:none}</style></head>
<body><main><p class="brand"><a href="/">Stationery Drop Watch</a></p><h1>${ok ? "Check your email" : "We couldn't sign you up"}</h1><p>${esc(message)}</p>${fallback}<a class="btn" href="/">Back to the site</a></main></body></html>`;
  return new Response(html, { status, headers: { ...headers, "content-type": "text/html; charset=utf-8" } });
}

async function readBody(request) {
  const ct = request.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    const j = await request.json();
    const tags = Array.isArray(j.tags) ? j.tags : Array.isArray(j["tags[]"]) ? j["tags[]"] : [];
    return { email: j.email_address || j.email, tags, token: j["cf-turnstile-response"] || j.token, trap: j.website };
  }
  const f = await request.formData();
  return { email: f.get("email_address"), tags: f.getAll("tags[]").concat(f.getAll("tags")), token: f.get("cf-turnstile-response"), trap: f.get("website") };
}

async function kit(env, path, body) {
  const r = await fetch(`${KIT_API}${path}`, {
    method: "POST",
    headers: { "X-Kit-Api-Key": env.KIT_API_KEY, "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try { data = await r.json(); } catch (_) { /* empty body */ }
  return { status: r.status, data };
}

export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== "POST") {
    if (request.method === "GET" || request.method === "HEAD") return Response.redirect(new URL("/#alerts", request.url).toString(), 303);
    return reply(request, 405, false, MSG.method);
  }
  const origin = request.headers.get("origin");
  if (origin && new URL(origin).host !== new URL(request.url).host) return reply(request, 403, false, MSG.origin);

  let body;
  try { body = await readBody(request); } catch (_) { return reply(request, 400, false, MSG.email); }

  // Honeypot: bots fill the hidden "website" field. Pretend it worked, do nothing.
  if (body.trap) return reply(request, 200, true, MSG.ok);

  const email = String(body.email || "").trim().toLowerCase();
  if (email.length > 254 || !EMAIL_RE.test(email)) return reply(request, 400, false, MSG.email);
  const tags = [...new Set(body.tags.map(String).filter((t) => Object.hasOwn(TAGS, t)))];
  if (!tags.length) return reply(request, 400, false, MSG.tags);

  if (!env.KIT_API_KEY || !env.TURNSTILE_SECRET) return reply(request, 503, false, MSG.upstream);
  if (!body.token) return reply(request, 400, false, MSG.check);
  const vf = new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: String(body.token) });
  const ip = request.headers.get("cf-connecting-ip");
  if (ip) vf.set("remoteip", ip);
  let verdict;
  try { verdict = await (await fetch(SITEVERIFY, { method: "POST", body: vf })).json(); } catch (_) { return reply(request, 502, false, MSG.upstream); }
  if (!verdict || !verdict.success) return reply(request, 400, false, MSG.check);

  try {
    const created = await kit(env, "/subscribers", { email_address: email, state: "inactive" });
    if (created.status !== 200 && created.status !== 201) {
      return created.status === 422 ? reply(request, 400, false, MSG.email) : reply(request, 502, false, MSG.upstream);
    }
    const sub = created.data.subscriber;
    // Already confirmed: leave their tags and state alone (anyone could type this address). The note in MSG.ok covers it.
    if (sub.state === "active") return reply(request, 200, true, MSG.ok);
    const added = await kit(env, `/forms/${KIT_FORM_ID}/subscribers/${sub.id}`, { referrer: "https://stationerydropwatch.com/" });
    if (added.status !== 200 && added.status !== 201) return reply(request, 502, false, MSG.upstream);
    for (const t of tags) {
      const tagged = await kit(env, `/tags/${t}/subscribers/${sub.id}`, {});
      if (tagged.status !== 200 && tagged.status !== 201) return reply(request, 502, false, MSG.upstream);
    }
  } catch (_) {
    return reply(request, 502, false, MSG.upstream);
  }
  return reply(request, 200, true, MSG.ok);
}
