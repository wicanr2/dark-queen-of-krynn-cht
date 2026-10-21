// 僅在既有 Playwright Chromium 容器內執行，以 DevTools pipe 驗證本機樣張。
import {spawn} from 'node:child_process';
import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';

const [page, output] = process.argv.slice(2);
const browser = spawn('/ms-playwright/chromium-1194/chrome-linux/chrome', [
  '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
  '--remote-debugging-pipe', '--user-data-dir=/tmp/dqk-map-browser', 'about:blank',
], {stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe']});
let nextId = 1, pending = new Map(), buffer = '', stderr = '';
browser.stderr.on('data', data => {stderr = (stderr + data).slice(-4000);});
browser.stdio[4].on('data', data => {
  buffer += data;
  for (;;) {
    const end = buffer.indexOf('\0');
    if (end < 0) break;
    const message = JSON.parse(buffer.slice(0, end));
    buffer = buffer.slice(end + 1);
    if (message.id && pending.has(message.id)) {
      const {resolve, reject} = pending.get(message.id); pending.delete(message.id);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result);
    }
  }
});
browser.on('exit', code => {
  for (const {reject} of pending.values()) reject(new Error(`Chromium 結束 ${code}: ${stderr}`));
  pending.clear();
});
function send(method, params = {}, sessionId) {
  return new Promise((resolve, reject) => {
    const id = nextId++; pending.set(id, {resolve, reject});
    browser.stdio[3].write(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}) + '\0');
  });
}
const timer = setTimeout(() => {browser.kill('SIGKILL'); process.exitCode = 1;}, 20000);
try {
  const version = await send('Browser.getVersion');
  const {targetId} = await send('Target.createTarget', {url: 'about:blank'});
  const {sessionId} = await send('Target.attachToTarget', {targetId, flatten: true});
  const call = (method, params) => send(method, params, sessionId);
  const evaluate = async expression => {
    const result = await call('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  await call('Page.enable');
  await call('Emulation.setDeviceMetricsOverride', {width: 1280, height: 1050, deviceScaleFactor: 1, mobile: false});
  await call('Page.navigate', {url: pathToFileURL(page).href});
  await evaluate(`new Promise(resolve=>{function ready(){if(document.readyState==='complete' &&
    document.getElementById('canvas'))document.fonts.ready.then(resolve);else setTimeout(ready,20);}ready();})`);
  const initial = await evaluate(`({points:document.querySelectorAll('.point').length,
    font:document.fonts.check('20px dqk-map'),images:document.querySelectorAll('svg image').length,
    transform:document.getElementById('canvas').style.transform})`);
  assert.equal(initial.points, 11); assert.equal(initial.font, true); assert.equal(initial.images, 0);
  const text = await evaluate(`document.querySelector('[data-point="10"]').dispatchEvent(
    new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));document.getElementById('detail').textContent`);
  assert.match(text, /Daenor/);
  assert.match(text, /來源/);
  const zoomed = await evaluate(`document.getElementById('plus').click();document.getElementById('canvas').style.transform`);
  assert.notEqual(zoomed, initial.transform);
  await call('Input.dispatchMouseEvent', {type:'mousePressed', x:1100,y:300,button:'left',clickCount:1});
  await call('Input.dispatchMouseEvent', {type:'mouseMoved', x:1140,y:340,button:'left',buttons:1});
  await call('Input.dispatchMouseEvent', {type:'mouseReleased', x:1140,y:340,button:'left',clickCount:1});
  const panned = await evaluate(`document.getElementById('canvas').style.transform`);
  assert.notEqual(panned, zoomed);
  await evaluate(`document.getElementById('fit').click()`);
  const location = await evaluate(`(()=>{const r=document.querySelector('[data-point="5"]')
    .getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  await call('Input.dispatchMouseEvent', {type:'mousePressed', ...location,button:'left',clickCount:1});
  await call('Input.dispatchMouseEvent', {type:'mouseReleased', ...location,button:'left',clickCount:1});
  const unknown = await evaluate(`document.getElementById('detail').textContent`);
  assert.match(unknown, /未附對應文字/);
  await evaluate(`document.getElementById('fit').click()`);
  const {data} = await call('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false});
  writeFileSync(`${output}/browser.png`, Buffer.from(data, 'base64'));
  const digest = bytes => createHash('sha256').update(bytes).digest('hex');
  const receipt = {browser: version, inputSha256: digest(readFileSync(page)),
    toolSha256: digest(readFileSync(new URL(import.meta.url))),
    checks: {font: true, vectorOnly: true, points: 11,
    keyboardDetails: true, zoom: true, pointerPan: true, unknownNotice: true}, initial, detail: text};
  writeFileSync(`${output}/browser-receipt.json`, JSON.stringify(receipt, null, 2)+'\n');
  console.log(JSON.stringify(receipt));
} finally {
  clearTimeout(timer); browser.kill('SIGTERM');
}
