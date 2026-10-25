"""One-off: build stores.json from discovered candidate product URLs.
Pool = product sitemap URLs containing 'hobonichi/techo' + '2027' (discover_*.json)
     + Shopify collection JSON (/collections/<slug>/products.json) for titles.
Each selected URL is then verified live via /products/<handle>.js (HTTP 200)."""
import json, re, time, glob, requests
UA="Mozilla/5.0 (compatible; DropWatchBot/0.1; +local-dev)"
S=requests.Session(); S.headers["User-Agent"]=UA

CANON=[ # (id, label, type, regex over "handle title")
 ("original-a6-en","Original A6 book (English)","Book", r"(original|a6[- ]planner|a6-size).*(english|eng)|english.*original.*book|english original"),
 ("cousin-a5-en","Cousin A5 book (English)","Book", r"cousin.*(english|eng).*book|english.*cousin.*book|cousin-a5-english|a5-cousin-english|a5-cousin-planner-book-only-english|english cousin book"),
 ("original-a6-jp","Original A6 book (Japanese)","Book", r"japanese.*original.*a6|original.*a6.*japanese|a6-original-avec-japanese|original book .*japanese"),
 ("weeks-midnight-blue","Weeks · Colors: Midnight Blue","Weeks", r"weeks(?!-mega)(?!.*mega).*midnight"),
 ("weeks-canaria-yellow","Weeks · Colors: Canaria Yellow","Weeks", r"weeks(?!.*mega).*canaria"),
 ("weeks-moomin-table","Weeks · Moomin: At the Table","Weeks", r"weeks.*moomin.*table"),
 ("weeks-white-cat","Weeks · Yumi Kitagishi: White Cat Wallpaper","Weeks", r"weeks.*white.cat.wallpaper"),
 ("weeks-mega-midnight-blue","Weeks Mega · Colors: Midnight Blue","Weeks Mega", r"mega.*midnight"),
 ("weeks-mega-candy-dream","Weeks Mega · Bow & Tie: Candy Dream","Weeks Mega", r"mega.*candy.dream"),
 ("cover-a6-moomin","A6 cover · Moomin: My Yard (Pale Mint)","Cover", r"cover.*moomin.*my.yard.*(pale.mint|a6)|moomin.*my.yard.*pale"),
 ("cover-a6-white-cat-house","A6 cover · Yumi Kitagishi: White Cat House","Cover", r"white.cat.house"),
 ("cover-a6-tragen-black","A6 cover · TRAGEN: Black","Cover", r"tragen.black"),
 ("cover-a6-mina-felice","A6 cover · mina perhonen: felice (Blue)","Cover", r"mina.perhonen.felice.*(a6|original)|original.*mina.perhonen.felice|a6.cover.mina.perhonen.felice"),
]
EXCL=r"preview-exhibit|launch-party|jibun|calendar|pencil-board|5-year|day-free|avec|refill-set|bundle|sticker|hon-"
STORES=[
 dict(id="1101",name="Hobonichi Online Store (official)",url="https://www.1101.com/store/techo/en/",country="JP (ships worldwide)",platform="hobonichi",indie=False),
 dict(id="papermouse",name="The Paper Mouse",url="https://www.thepapermouse.com/",country="US",platform="shopify",indie=True,sitemap="thepapermouse.com",cols=["hobonichi","hobonichi-techo","hobonichi-2027"]),
 dict(id="atlas",name="Atlas Stationers",url="https://www.atlasstationers.com/",country="US",platform="shopify",indie=True,evergreen=True,sitemap="atlas",cols=["hobonichi","hobonichi-techo","hobonichi-2027","hobonichi-techo-2027"]),
 dict(id="bobo",name="Bobo Design Studio",url="https://bobodesignstudio.com/",country="US",platform="shopify",indie=True,sitemap="bobo",cols=["hobonichi","hobonichi-techo"]),
 dict(id="baum",name="Baum-kuchen",url="https://www.baum-kuchen.net/",country="US",platform="shopify",indie=True,sitemap="baum",cols=["hobonichi"]),
 dict(id="wonder",name="Wonder Pens",url="https://wonderpens.ca/",country="CA",platform="shopify",indie=True,sitemap="wonder",cols=["hobonichi"]),
 dict(id="laywines",name="Laywine's",url="https://laywines.com/",country="CA",platform="shopify",indie=True,sitemap="laywines",cols=["hobonichi"]),
 dict(id="penboutique",name="Pen Boutique",url="https://www.penboutique.com/",country="US",platform="shopify",indie=True,sitemap="penboutique",cols=["hobonichi","hobonichi-techo"]),
 dict(id="yoseka",name="Yoseka Stationery",url="https://yosekastationery.com/",country="US",platform="shopify",indie=True,sitemap="yoseka",cols=["hobonichi"]),
 dict(id="jennibick",name="Jenni Bick",url="https://www.jennibick.com/",country="US",platform="shopify",indie=True,sitemap="jennibick",cols=["hobonichi"]),
 dict(id="kinousa",name="Kinokuniya USA",url="https://usa.kinokuniya.com/",country="US",platform="shopify",indie=False,cols=["hobonichi-techo"]),
 dict(id="kinosg",name="Kinokuniya Singapore",url="https://kinokuniya.com.sg/",country="SG",platform="shopify",indie=False,cols=["hobonichi-techo"]),
 dict(id="omoi",name="Omoi Zakka Shop",url="https://omoionline.com/",country="US",platform="shopify",indie=True,cols=["hobonichi"]),
 dict(id="jetpens",name="JetPens",url="https://www.jetpens.com/",country="US",platform="blocked",indie=False,note="Returns HTTP 403 to non-browser requests (bot protection). Listed as a link only; not checked."),
 dict(id="nanami",name="Nanami Paper",url="https://www.nanamipaper.com/",country="US",platform="robots-disallow",indie=True,note="robots.txt disallows all crawling (User-agent: * / Disallow: /). Listed as a link only; not checked."),
]
def pool_for(s):
    base=s["url"].rstrip("/"); P={}
    if s.get("sitemap"):
        for f in glob.glob(f"discover_{s['sitemap']}.json"):
            for v in json.load(open(f)).values():
                for u in v["h27"]: h=u.split("/products/")[1]; P[h]=h.replace("-"," ")
    for c in s.get("cols",[]):
        for page in (1,2):
            try:
                r=S.get(f"{base}/collections/{c}/products.json?limit=250&page={page}",timeout=25); time.sleep(1.2)
                if not r.ok: break
                ps=r.json().get("products",[])
                for p in ps:
                    if "2027" in p["title"]+p["handle"] or (s.get("evergreen") and "hobonichi techo" in p["title"].lower() and "2027" in (p.get("body_html") or "")): P[p["handle"]]=p["handle"].replace("-"," ")+" | "+p["title"]
                if len(ps)<250: break
            except Exception: break
    return base,P
out=[]
for s in STORES:
    s=dict(s); s["products"]=[]
    if s["platform"]=="hobonichi":
        items=json.load(open("items27.json"))["items"]
        for cid,key in [("original-a6-en","ob27_jan_en"),("cousin-a5-en","cb27_jan_en"),("original-a6-jp","ob27_jan"),("weeks-midnight-blue","wb27_colorsmblue"),("weeks-moomin-table","wb27_moomintable"),("weeks-white-cat","wb27_kitagishi"),("weeks-mega-candy-dream","wb27_m_tiecandy"),("cover-a6-moomin","oc27_moomin")]:
            c=next(x for x in CANON if x[0]==cid); it=items[key]
            u=f"https://www.1101.com/store/techo/en/2027/pc/detail_cover/{key}/"
            code=S.get(u,timeout=25).status_code; time.sleep(1.5)
            if code==200: s["products"].append(dict(canonical=cid,label=c[1],type=c[2],url=u,source_key=key,source_title=it["title2"]["en"]))
        out.append(s); print(s["id"],len(s["products"]),flush=True); continue
    if s["platform"]!="shopify": out.append(s); print(s["id"],"link-only"); continue
    base,P=pool_for(s)
    for cid,label,typ,rx in CANON:
        if len(s["products"])>=8: break
        cands=[h for h,t in P.items() if re.search(rx,(h+" "+t).lower()) and not re.search(EXCL,h) and not (typ=="Book" and "cover" in (h+" "+t).lower())]
        cands.sort(key=lambda h:("preview" in h, ("japanese" in h) and "jp" not in cid, "one-piece" in h, len(h)))
        for h in cands[:2]:
            r=S.get(f"{base}/products/{h}.js",timeout=25); time.sleep(1.2)
            if r.ok:
                s["products"].append(dict(canonical=cid,label=label,type=typ,url=f"{base}/products/{h}",source_title=r.json().get("title"))); break
    out.append(s); print(s["id"],len(P),len(s["products"]),flush=True)
json.dump({"generated":time.strftime("%Y-%m-%dT%H:%M:%S%z"),"canonical":[dict(id=a,label=b,type=c) for a,b,c,_ in CANON],"stores":out},open("stores.json","w"),indent=1,ensure_ascii=False)
