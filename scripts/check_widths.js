const { chromium } = require("playwright-core");const fs=require("fs"),path=require("path");
const R="/workspace/draft-hub-site";const files=[];(function w(d){for(const f of fs.readdirSync(d)){const p=path.join(d,f);if(fs.statSync(p).isDirectory())w(p);else if(f.endsWith(".html")&&!fs.readFileSync(p,"utf8").includes('http-equiv="refresh"'))files.push("/"+path.relative(R,p).replace(/index\.html$/,""))}})(R);
(async()=>{const b=await chromium.launch({executablePath:"/usr/bin/google-chrome"});const p=await b.newPage({viewport:{width:1440,height:900}});let bad=0;
for(const u of files.sort()){try{await p.goto("http://localhost:8765"+u,{waitUntil:"load"});await p.waitForTimeout(150);if(!p.url().endsWith(u)){console.log("redir "+u+" -> "+p.url());continue}

const r=await p.evaluate(()=>{const m=document.querySelector("main");const rt=e=>{if(!e)return"-";const g=document.createRange();g.selectNodeContents(e);const t=Math.round(Math.max(...[...g.getClientRects()].map(x=>x.right)));return Math.round(e.getBoundingClientRect().right)+"/text"+t};
const h=m.querySelector("h1");const l=m.querySelector(".lede")||m.querySelector("h1 ~ p");
let wide=0,narrow=[];for(const e of m.querySelectorAll("p,ul,ol,h2,section,article,div.prose,details")){const r=e.getBoundingClientRect();if(r.width<5||e.closest("table,.hub-grid,.shop-list,.follow-list,.stats,form,li,.cards,nav,.hub-own-row,figure"))continue;const x=Math.round(r.right);if(x>wide)wide=x;const pe=e.parentElement,pr=pe.getBoundingClientRect().right-parseFloat(getComputedStyle(pe).paddingRight);if(pr-x>16&&!["grid","flex"].includes(getComputedStyle(pe).display))narrow.push(x+":"+(e.className||e.parentElement.className||e.tagName))}
return [rt(h),rt(l),wide,narrow.slice(0,3).join(" ")]});
const f=(parseInt(r[0])<1280||parseInt(r[1])<1280||r[3]);if(f)bad++;console.log((f?"FLAG ":"ok   ")+u+"\th1 "+r[0]+"\tintro "+r[1]+"\twidest "+r[2]+"\t"+r[3])}catch(err){console.log("err "+u+" "+err.message.slice(0,60))}}
console.log("flagged",bad);await b.close()})();
