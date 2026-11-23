"""Policy-audit wording: confirmation, one signup promise, HON/Planner A6, TpT, typo, GitHub."""
import html
import json
import re
import unittest

import scripts.build_site as site


CONFIRM = "We'll email you a confirmation link. You aren't on the list until you click it."
NOTE = (
    "Free restock emails for the trackers you pick: Hobonichi, dot grid journals and limited-edition inks. "
    "Pick at least one, plus an occasional update when we add a tracker or release something new. "
    "Unsubscribe anytime. We'll email you a confirmation link. You aren't on the list until you click it."
)
ALERTS_FAQ = (
    "Sign up with your email and we'll send a confirmation link. Once you confirm, you'll get free restock emails for the trackers you pick: Hobonichi, dot grid journals and limited-edition inks, plus an occasional update when we add a tracker or release something new. "
    "Ink restocks also show on the inks page. "
    "You can unsubscribe anytime."
)
TRACK_HOBO = "Hobonichi Techo 2027: the Original A6 and Cousin A5 books, the English Planner A6 book, HON, Weeks and Weeks Mega, and 15 A6 covers, 12 A5 covers and 3 Weeks covers."
HUB_HOBO = "Original A6, Cousin A5, the English Planner A6, HON, Weeks, Weeks Mega and covers, at the official store and independent shops."
SELL_TPT = "Classroom printables are on Teachers Pay Teachers."
OUTBOUND = "When you follow a link to a shop we track, or to Amazon, Etsy, or Teachers Pay Teachers for our own planners, journals, and printables, that site has its own privacy policy."
GITHUB = "The source code, the checker, and a backup copy of the site are hosted on GitHub (GitHub Pages)."


def html_of(built):
    return built[1] if isinstance(built, tuple) else built


def faq_schema_text(doc, question):
    start = doc.rfind("<script", 0, doc.index('"@type": "FAQPage"'))
    end = doc.index("</script>", start)
    schema = json.loads(html.unescape(doc[start:end].split(">", 1)[1].replace("<\\/", "</")))
    for item in schema["mainEntity"]:
        if item["name"] == question:
            return item["acceptedAnswer"]["text"]
    raise AssertionError(f"question not in schema: {question}")


def visible_answer(doc, question):
    m = re.search(
        rf'<details class="faq-item"><summary>{re.escape(site.E(question))}</summary><p>(.*?)</p></details>',
        doc, flags=re.S)
    if not m:
        raise AssertionError(f"question not on page: {question}")
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))


class PolicyWordingTests(unittest.TestCase):
    def test_every_signup_box_uses_the_same_honest_note(self):
        self.assertEqual(site.LIST_LINE, NOTE)
        self.assertEqual(site.SIGNUP_COPY["alerts"][1], NOTE)
        self.assertEqual(site.SIGNUP_COPY["shop"][1], NOTE)
        pages = {
            "home": html_of(site.build_index()),
            "about": html_of(site.build_about()),
            "follow": html_of(site.build_follow()),
            "shop": html_of(site.build_shop()),
            "hobonichi": html_of(site.build_hobo_tracker()),
        }
        for name, doc in pages.items():
            notes = [html.unescape(n) for n in re.findall(r'class="strip-note">(.*?)</p>', doc)]
            self.assertTrue(notes, name)
            for note in notes:
                self.assertIn(NOTE, note, name)
                self.assertIn(CONFIRM, note, name)
                self.assertNotIn("Hear about new planners", note, name)
                self.assertNotIn("No spam", note, name)

    def test_homepage_faq_and_schema_stay_in_sync(self):
        home = html_of(site.build_index())
        for q, needles in (
            ("How do restock alerts work?", (ALERTS_FAQ,)),
            ("What do you track?", (TRACK_HOBO, "the English Planner A6 book", "HON")),
            ("Do you sell planners?", (SELL_TPT,)),
            ("Which shops do you check?", ("11 independent shops.",)),
        ):
            visible = visible_answer(home, q)
            schema = faq_schema_text(home, q)
            for needle in needles:
                self.assertIn(needle, visible, q)
                self.assertIn(needle, schema, q)
            self.assertNotIn("shops..", visible, q)
            self.assertNotIn("shops..", schema, q)
        self.assertIn(HUB_HOBO, home)

    def test_product_and_guide_alert_faqs_mention_confirmation(self):
        d = site.DESIGNS[0]
        design = html_of(site.build_design(d, None))
        vis = visible_answer(design, "Can I get restock alerts?")
        sch = faq_schema_text(design, "Can I get restock alerts?")
        for text in (vis, sch):
            self.assertIn("confirmation link", text)
            self.assertIn("you aren't on the list until you click it", text)
            self.assertIn("occasional update", text)
            self.assertIn(d["full"], text)
        wtb = html_of(site.build_where_to_buy())
        wtb_vis = visible_answer(wtb, "How do I get told when something restocks?")
        wtb_sch = faq_schema_text(wtb, "How do I get told when something restocks?")
        for text in (wtb_vis, wtb_sch):
            self.assertIn("confirmation link", text)
            self.assertIn("occasional update", text)
        dg = html_of(site.build_dotgrid_guide())
        dg_vis = visible_answer(dg, "How do the email alerts work?")
        dg_sch = faq_schema_text(dg, "How do the email alerts work?")
        for text in (dg_vis, dg_sch):
            self.assertIn("confirmation link", text)
            self.assertIn("occasional update", text)

    def test_privacy_discloses_confirmation_tpt_and_github(self):
        doc = html_of(site.build_privacy())
        text = html.unescape(re.sub(r"<[^>]+>", " ", doc))
        self.assertIn("updated Nov 22, 2026", text)
        self.assertEqual(site.STATIC_LASTMOD["privacy/"], "2026-11-22")
        self.assertIn("Cloudflare Web Analytics", text)
        self.assertIn("does not track individual end users across its customers", text)
        self.assertNotIn("does not currently run analytics beacons", text)
        self.assertIn("The site is hosted on Cloudflare Pages.", text)
        self.assertIn("Kit sends a confirmation email first", text)
        self.assertIn("we only add the address to the list after you click the link", text)
        self.assertIn("We use it only to send restock alerts for the trackers you chose and occasional site updates.", text)
        self.assertIn(OUTBOUND, text)
        self.assertIn(GITHUB, text)
        self.assertNotIn("Amazon or Etsy for our own planners and journals,", text)
        self.assertNotIn("the alerts and occasional updates you signed up for", text)


if __name__ == "__main__":
    unittest.main()
