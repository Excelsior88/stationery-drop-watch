const { chromium } = require("playwright-core");const fs=require("fs"),path=require("path");
const R="/workspace/draft-hub-site";const files=[];(function w(d){for(const f of fs.readdirSync(d)){const p=path.join(d,f);if(fs.statSync(p).isDirectory())w(p);else if(f.endsWith(".html")&&!fs.readFileSync(p,"utf8").includes('http-equiv="refresh"'))files.push("/"+path.relative(R,p).replace(/index\.html$/,""))}})(R);
(async()=>{const b=await chromium.launch({executablePath:"/usr/bin/google-chrome"});const p=await b.newPage({viewport:{width:1440,height:900}});let bad=0;
for(const u of files.sort()){try{await p.goto("http://localhost:8765"+u,{waitUntil:"load"});await p.waitForTimeout(150);if(!p.url().endsWith(u)){console.log("redir "+u+" -> "+p.url());continue}

const r=await p.evaluate(()=>{const m=document.querySelector("main");const rt=e=>{if(!e)return"-";const g=document.createRange();g.selectNodeContents(e);const t=Math.round(Math.max(...[...g.getClientRects()].map(x=>x.right)));return Math.round(e.getBoundingClientRect().right)+"/text"+t};
const h=m.querySelector("h1");const l=m.querySelector(".lede")||m.querySelector("h1 ~ p");
let wide=0,narrow=[];for(const e of m.querySelectorAll("p,ul,ol,h2,section,article,div.prose,details")){const r=e.getBoundingClientRect();if(r.width<5||e.closest("table,.hub-grid,.shop-list,.follow-list,.stats,form,li,.cards,nav,.hub-own-row,figure"))continue;const x=Math.round(r.right);if(x>wide)wide=x;const pe=e.parentElement,pr=pe.getBoundingClientRect().right-parseFloat(getComputedStyle(pe).paddingRight);if(pr-x>16&&!["grid","flex"].includes(getComputedStyle(pe).display))narrow.push(x+":"+(e.className||e.parentElement.className||e.tagName))}
let hs="";if(h){const br=h.getBoundingClientRect(),ws=[];const tw=document.createTreeWalker(h,NodeFilter.SHOW_TEXT);let n;while(n=tw.nextNode()){const re=/\S+/g;let m;while(m=re.exec(n.data)){const g=document.createRange();g.setStart(n,m.index);g.setEnd(n,m.index+m[0].length);const r=g.getBoundingClientRect();ws.push(r)}}
/* fail when a line ends well short of the content width (>15%) although the next line's first word would have fit there */
for(let i=1;i<ws.length;i++){if(Math.round(ws[i].top)>Math.round(ws[i-1].top)+4){const gap=br.right-ws[i-1].right;if(gap>0.15*br.width&&gap>ws[i].width+20){hs=" h1-short:"+Math.round(ws[i-1].right-br.left)+"of"+Math.round(br.width);break}}}}
return [rt(h),rt(l),wide,(narrow.slice(0,3).join(" ")+hs).trim()]});
const f=(parseInt(r[0])<1280||parseInt(r[1])<1280||r[3]);if(f)bad++;console.log((f?"FLAG ":"ok   ")+u+"\th1 "+r[0]+"\tintro "+r[1]+"\twidest "+r[2]+"\t"+r[3])}catch(err){console.log("err "+u+" "+err.message.slice(0,60))}}
console.log("flagged",bad);await b.close()})();
