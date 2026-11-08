/* Restock and last-check instants. The HTML text is Eastern Time. This rewrites only
   time.time-instant elements into the visitor's zone. Editorial dates are not marked and stay put.
   A missing zone, a bad timestamp, or any thrown error leaves the Eastern Time text. */
(function (root) {
  function formatInstant(iso, timeZone, locale, now) {
    if (typeof iso !== "string" || iso.indexOf("T") < 0) return null;
    var date = new Date(iso);
    if (isNaN(date.getTime())) return null;
    if (!timeZone) return null;
    var nowDate = now ? new Date(now) : new Date();
    if (isNaN(nowDate.getTime())) nowDate = new Date();
    var loc = locale || "en-US";
    try {
      var yearFmt = new Intl.DateTimeFormat("en-US", { timeZone: timeZone, year: "numeric" });
      var showYear = yearFmt.format(date) !== yearFmt.format(nowDate);
      var opt = {
        timeZone: timeZone, month: "short", day: "numeric",
        hour: "numeric", minute: "2-digit", hour12: true, timeZoneName: "short"
      };
      if (showYear) opt.year = "numeric";
      var parts = new Intl.DateTimeFormat(loc, opt).formatToParts(date);
    } catch (e) {
      return null;
    }
    function val(type) {
      var out = "";
      for (var i = 0; i < parts.length; i++) if (parts[i].type === type) out += parts[i].value;
      return out;
    }
    var month = val("month"), day = val("day"), year = val("year");
    var hour = val("hour"), minute = val("minute"), period = val("dayPeriod"), zone = val("timeZoneName");
    if (!month || !day || !hour || !minute || !zone) return null;
    var datePart = year ? month + " " + day + ", " + year : month + " " + day;
    var clock = period ? hour + ":" + minute + " " + period : hour + ":" + minute;
    return datePart + ", " + clock + " " + zone;
  }

  function applyLocalTimes(doc, timeZone, locale, now) {
    if (!doc || !doc.querySelectorAll || !timeZone) return 0;
    var nodes = doc.querySelectorAll("time.time-instant[datetime]");
    var n = 0;
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var text = formatInstant(el.getAttribute("datetime"), timeZone, locale, now);
      if (!text) continue;
      el.textContent = text;
      n++;
    }
    return n;
  }

  function showLocalTimes(doc) {
    try {
      var zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (!zone) return;
      applyLocalTimes(doc || root.document, zone, (root.navigator && root.navigator.language) || "en-US");
    } catch (e) {}
  }

  var api = { formatInstant: formatInstant, applyLocalTimes: applyLocalTimes, showLocalTimes: showLocalTimes };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.DropWatchTime = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
