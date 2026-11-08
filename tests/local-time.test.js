"use strict";
const assert = require("assert");
const { formatInstant, applyLocalTimes } = require("../site/assets/local-time.js");

const NOW = "2026-06-15T15:00:00Z";

function at(iso, zone) {
  return formatInstant(iso, zone, "en-US", NOW);
}

assert.equal(at("2026-11-08T08:14:52Z", "America/New_York"), "Nov 8, 3:14 AM EST");
assert.equal(at("2026-11-08T08:14:52Z", "America/Los_Angeles"), "Nov 8, 12:14 AM PST");
assert.equal(at("2026-11-08T08:14:52Z", "Europe/London"), "Nov 8, 8:14 AM GMT");
assert.equal(at("2026-11-08T08:14:52Z", "Asia/Tokyo"), "Nov 8, 5:14 PM GMT+9");

// US spring-forward, 2026-03-08. 06:30Z is still EST. 07:30Z is EDT.
assert.equal(at("2026-03-08T06:30:00Z", "America/New_York"), "Mar 8, 1:30 AM EST");
assert.equal(at("2026-03-08T07:30:00Z", "America/New_York"), "Mar 8, 3:30 AM EDT");
// US fall-back, 2026-11-01. 05:30Z is still EDT. 06:30Z is EST.
assert.equal(at("2026-11-01T05:30:00Z", "America/New_York"), "Nov 1, 1:30 AM EDT");
assert.equal(at("2026-11-01T06:30:00Z", "America/New_York"), "Nov 1, 1:30 AM EST");

// Same instant, previous local date in New York and the same calendar day in Tokyo.
assert.equal(at("2026-11-08T04:30:00Z", "America/New_York"), "Nov 7, 11:30 PM EST");
assert.equal(at("2026-11-08T04:30:00Z", "Asia/Tokyo"), "Nov 8, 1:30 PM GMT+9");

// Year boundary. The frozen "now" is 2026, so 2025 is shown.
assert.equal(at("2026-01-01T04:30:00Z", "America/New_York"), "Dec 31, 2025, 11:30 PM EST");
assert.equal(at("2026-01-01T04:30:00Z", "Asia/Tokyo"), "Jan 1, 1:30 PM GMT+9");

for (const bad of ["", "2026-11-08", "not-a-time", "2026-13-40T00:00:00Z", null, undefined]) {
  assert.equal(formatInstant(bad, "America/New_York", "en-US", NOW), null);
}
assert.equal(formatInstant("2026-11-08T08:14:52Z", "", "en-US", NOW), null);
assert.equal(formatInstant("2026-11-08T08:14:52Z", "Not/AZone", "en-US", NOW), null);

function el(attrs, text) {
  const attributes = Object.assign({}, attrs);
  return {
    getAttribute(name) { return attributes[name] || null; },
    textContent: text
  };
}
const editorial = el({}, "Aug 25, 2026");
const instant = el({ class: "time-instant", datetime: "2026-11-08T08:14:52Z" }, "Nov 8, 3:14 AM ET");
const broken = el({ class: "time-instant", datetime: "nope" }, "Nov 8, 3:14 AM ET");
const root = {
  querySelectorAll(sel) {
    assert.equal(sel, "time.time-instant[datetime]");
    return [instant, broken];
  }
};
assert.equal(applyLocalTimes(root, "Asia/Tokyo", "en-US", NOW), 1);
assert.equal(instant.textContent, "Nov 8, 5:14 PM GMT+9");
assert.equal(instant.getAttribute("datetime"), "2026-11-08T08:14:52Z");
assert.equal(broken.textContent, "Nov 8, 3:14 AM ET");
assert.equal(editorial.textContent, "Aug 25, 2026");
assert.equal(applyLocalTimes(root, "", "en-US", NOW), 0);

console.log("local-time tests ok");
