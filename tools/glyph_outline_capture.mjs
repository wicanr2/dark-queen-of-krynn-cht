// 固定 Chromium 的本機 SVG 原尺寸擷取，不使用字型替代或圖像縮放。
import {spawn} from 'node:child_process';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {join} from 'node:path';
import assert from 'node:assert/strict';
const [directory]=process.argv.slice(2);
const data=JSON.parse(readFileSync(join(directory,'outline-source.json')));
const browser=spawn('/ms-playwright/chromium-1194/chrome-linux/chrome',[
  '--headless','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--hide-scrollbars',
  '--remote-debugging-pipe','--user-data-dir=/tmp/dqk-glyph-outline','about:blank',
],{stdio:['ignore','ignore','pipe','pipe','pipe']});
let next=1,buffer='';const waiting=new Map();
browser.stdio[4].on('data',chunk=>{buffer+=chunk;for(;;){const n=buffer.indexOf('\0');if(n<0)break;
  const message=JSON.parse(buffer.slice(0,n));buffer=buffer.slice(n+1);const p=waiting.get(message.id);
  if(p){waiting.delete(message.id);message.error?p.reject(new Error(JSON.stringify(message.error))):p.resolve(message.result);}
}});
const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const id=next++;waiting.set(id,{resolve,reject});browser.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+'\0');});
const deadline=setTimeout(()=>{browser.kill('SIGKILL');process.exit(2);},20000);
try{
  const {targetId}=await send('Target.createTarget',{url:'about:blank'});
  const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
  await send('Page.enable',{},sessionId);
  await send('Emulation.setDeviceMetricsOverride',{width:16,height:20,deviceScaleFactor:1,mobile:false},sessionId);
  const version=await send('Browser.getVersion');
  for(const glyph of data.glyphs){
    const target=join(directory,glyph.svg.replace('.svg','.png'));assert(!existsSync(target));
    const url=pathToFileURL(join(directory,glyph.svg)).href;
    await send('Page.navigate',{url},sessionId);
    for(let i=0;i<100;i++){
      const {result}=await send('Runtime.evaluate',{expression:'document.readyState+":"+document.documentElement.tagName+":"+document.URL',returnByValue:true},sessionId);
      if(result.value==='complete:svg:'+url)break;
      await new Promise(resolve=>setTimeout(resolve,10));
      assert(i<99,'SVG load timeout');
    }
    const {data:png}=await send('Page.captureScreenshot',{format:'png',clip:{x:0,y:0,width:16,height:20,scale:1}},sessionId);
    writeFileSync(target,Buffer.from(png,'base64'));
  }
  writeFileSync(join(directory,'outline-browser.json'),JSON.stringify(version,null,2)+'\n');
}finally{clearTimeout(deadline);await send('Browser.close').catch(()=>{});browser.kill('SIGTERM');}
