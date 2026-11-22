// Runs site/functions/api/subscribe.js against a mocked fetch (no network). Exit code 1 on any failed check.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import path from "node:path";
const fn = await import(pathToFileURL(path.resolve(import.meta.dirname, "../site/functions/api/subscribe.js")).href);

let calls = [];
let state = "inactive";
let turnstileOk = true;
globalThis.fetch = async (url, init) => {
  url = String(url);
  calls.push({ url, init });
  const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json" } });
  if (url.includes("siteverify")) return json({ success: turnstileOk });
  if (url.endsWith("/v4/subscribers")) return json({ subscriber: { id: 7, state, email_address: "a@b.co" } }, 201);
  if (url.includes("/v4/forms/10225471/subscribers/7")) return json({ subscriber: { id: 7 } }, 201);
  if (/\/v4\/tags\/\d+\/subscribers\/7/.test(url)) return json({ subscriber: { id: 7 } }, 201);
  return json({}, 404);
};
const env = { KIT_API_KEY: "k", TURNSTILE_SECRET: "s" };
const post = (fields, headers = {}) => {
  const f = new FormData();
  for (const [k, v] of fields) f.append(k, v);
  return fn.onRequest({ env, request: new Request("https://stationerydropwatch.com/api/subscribe", { method: "POST", body: f, headers: { accept: "application/json", ...headers } }) });
};
const base = [["email_address", "A@B.co"], ["tags[]", "26280763"], ["tags[]", "26280765"], ["cf-turnstile-response", "tok"]];
const reset = () => { calls = []; state = "inactive"; turnstileOk = true; };

// happy path: siteverify, create inactive, add to form, tag twice
reset();
let r = await post(base); let j = await r.json();
assert.equal(r.status, 200); assert.equal(j.ok, true);
assert.equal(calls.length, 5);
assert.ok(calls[0].url.includes("siteverify"));
assert.equal(JSON.parse(calls[1].init.body).state, "inactive");
assert.equal(JSON.parse(calls[1].init.body).email_address, "a@b.co");
assert.ok(calls[2].url.endsWith("/forms/10225471/subscribers/7"));
assert.deepEqual(calls.slice(3).map(c => c.url.match(/tags\/(\d+)/)[1]), ["26280763", "26280765"]);
assert.equal(calls[1].init.headers["X-Kit-Api-Key"], "k");

// unknown tag ids are dropped; only unknown -> 400 and no Kit call
reset(); r = await post([["email_address", "a@b.co"], ["tags[]", "999"], ["cf-turnstile-response", "t"]]);
assert.equal(r.status, 400); assert.equal(calls.length, 0);
reset(); await post([["email_address", "a@b.co"], ["tags[]", "999"], ["tags[]", "26280764"], ["cf-turnstile-response", "t"]]);
assert.deepEqual(calls.slice(3).map(c => c.url.match(/tags\/(\d+)/)[1]), ["26280764"]);

// bad email, no token, failed turnstile, honeypot
reset(); r = await post([["email_address", "nope"], ["tags[]", "26280763"], ["cf-turnstile-response", "t"]]); assert.equal(r.status, 400); assert.equal(calls.length, 0);
reset(); r = await post([["email_address", "a@b.co"], ["tags[]", "26280763"]]); assert.equal(r.status, 400); assert.equal(calls.length, 0);
reset(); turnstileOk = false; r = await post(base); assert.equal(r.status, 400); assert.equal(calls.length, 1);
reset(); r = await post([...base, ["website", "http://spam"]]); assert.equal(r.status, 200); assert.equal(calls.length, 0);

// already active: no form add, no tag changes
reset(); state = "active"; r = await post(base); assert.equal(r.status, 200); assert.equal(calls.length, 2);

// unsubscribed before: Kit's API can't re-confirm them, so point to Kit's own form and change nothing
reset(); state = "cancelled"; r = await post(base); j = await r.json(); assert.equal(r.status, 200); assert.equal(j.ok, false); assert.match(j.rejoin, /kit\.com/); assert.equal(calls.length, 2);

// cross-origin refused
reset(); r = await post(base, { origin: "https://evil.example" }); assert.equal(r.status, 403); assert.equal(calls.length, 0);

// no-JS fallback returns branded HTML
reset(); r = await post(base, { accept: "text/html" });
assert.match(r.headers.get("content-type"), /text\/html/); assert.match(await r.text(), /Check your email/);
reset(); r = await post([["email_address", "x"]], { accept: "text/html" });
assert.equal(r.status, 400); assert.match(await r.text(), /Stationery Drop Watch/);

// Kit failure -> friendly 502, no secrets leaked
reset(); const real = globalThis.fetch;
globalThis.fetch = async (u) => String(u).includes("siteverify") ? new Response(JSON.stringify({ success: true })) : new Response("{}", { status: 500 });
r = await post(base); j = await r.json(); assert.equal(r.status, 502); assert.equal(j.ok, false); assert.ok(!JSON.stringify(j).includes("X-Kit"));
globalThis.fetch = real;

// GET redirects to the box
r = await fn.onRequest({ env, request: new Request("https://stationerydropwatch.com/api/subscribe") });
assert.equal(r.status, 303);
console.log("subscribe function: all checks passed");
