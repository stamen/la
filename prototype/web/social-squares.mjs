// Render the square social images in docs/social/ (1080x1080 at 2x = 2160 px JPEGs).
//
//   node prototype/web/social-squares.mjs [SITE_URL] [NAME_PREFIX]
//
// SITE_URL defaults to the live site, so no local tiles are needed; pass
// http://localhost:8080/ (node prototype/web/serve.mjs 8080) to render from a local checkout.
// NAME_PREFIX renders only the shots whose names start with it (e.g. 02).
import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const require = createRequire(import.meta.url);
let pw;
try { pw = require('playwright'); } catch { pw = require(path.join(execSync('npm root -g').toString().trim(), 'playwright')); }

const site = (process.argv[2] || 'https://la.stamen.com/').replace(/\/?$/, '/');
const only = process.argv[3];
const outDir = path.join(root, 'docs', 'social');

// hover: a screen point to search around for the largest building, which is then hovered.
// panel: keep the info panel open (the others hide all controls).
const SHOTS = [
  { name: '01-downtown', q: '', hash: '#12.3/34.045/-118.255' },
  { name: '02-county', q: '', hash: '#9.0/34.26/-118.29' },
  { name: '03-port', q: '', hash: '#12.6/33.758/-118.235' },
  { name: '04-hover', q: '', hash: '#16.6/34.0605/-118.2985', hover: [727, 671] },
  { name: '05-this-view', q: '?scale=view', hash: '#15.3/34.0615/-118.3005', panel: true },
  { name: '06-tomato-hills', q: '?background=tomato', hash: '#13.6/34.085/-118.405' },
  { name: '07-labels-steelblue', q: '?background=steelblue&labels=true', hash: '#13.4/34.02/-118.47' },
];

fs.mkdirSync(outDir, { recursive: true });
const browser = await pw.chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
for (const s of SHOTS.filter((x) => !only || x.name.startsWith(only))) {
  const page = await browser.newPage({ viewport: { width: 1080, height: 1080 }, deviceScaleFactor: 2 });
  await page.goto(site + s.q + s.hash);
  await page.waitForFunction(() => window.__map);
  await page.addStyleTag({ content: `${s.panel ? '' : '#info,'} #status, .maplibregl-control-container { display: none !important; }` });
  if (s.panel) await page.evaluate(() => { document.getElementById('info').open = true; });
  // Wait for tiles, then again after labels and the scale have had time to load and recolor.
  const loaded = () => page.waitForFunction(() => window.__map.loaded() && window.__map.areTilesLoaded(), null, { timeout: 120000 });
  await loaded(); await page.waitForTimeout(2500); await loaded(); await page.waitForTimeout(800);
  if (s.hover) {
    const pt = await page.evaluate(([cx, cy]) => {
      let best = null;
      for (let y = cy - 90; y <= cy + 90; y += 6) for (let x = cx - 90; x <= cx + 90; x += 6) {
        const f = window.__map.queryRenderedFeatures([x, y], { layers: ['buildings'] })[0];
        const d = Math.hypot(x - cx, y - cy);
        if (f && (!best || f.properties.a > best[2] || (f.properties.a === best[2] && d < best[3]))) best = [x, y, f.properties.a, d];
      }
      return best;
    }, s.hover);
    if (pt) { await page.mouse.move(pt[0], pt[1]); await page.waitForTimeout(500); }
  }
  const out = path.join(outDir, `${s.name}.jpg`);
  await page.screenshot({ path: out, type: 'jpeg', quality: 85 });
  console.log(`wrote ${out}`);
  await page.close();
}
await browser.close();
