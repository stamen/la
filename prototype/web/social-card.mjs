// Render the social card (social.jpg at the repo root, 1200x630) from the map itself.
//
//   node prototype/web/social-card.mjs [SITE_URL]
//
// SITE_URL defaults to the live site, so no local tiles are needed; pass
// http://localhost:8080/ (node prototype/web/serve.mjs 8080) to render from a local checkout.
import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const require = createRequire(import.meta.url);
let pw;
try { pw = require('playwright'); } catch { pw = require(path.join(execSync('npm root -g').toString().trim(), 'playwright')); }

const site = (process.argv[2] || 'https://la.stamen.com/').replace(/\/?$/, '/');
const VIEW = '#12/34.050/-118.270';  // downtown, the river and the freeways

const browser = await pw.chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
await page.goto(site + VIEW);
await page.addStyleTag({ content: `
  #info, #status, #tip, .maplibregl-control-container { display: none !important; }
  #card { position: fixed; left: 48px; bottom: 48px; z-index: 5; padding: 26px 30px 24px; max-width: 640px;
    background: var(--panel); border: 1px solid var(--panel-line); border-radius: 6px; color: var(--ink); }
  #card h2 { margin: 0; font: 700 54px/1.05 var(--font-display); letter-spacing: -0.01em; }
  #card p { margin: 14px 0 0; font: 400 22px/1.35 var(--font-display); }
  #card .by { margin-top: 18px; font: 500 15px var(--font-data); text-transform: uppercase; letter-spacing: 0.12em; color: var(--ink-dim); }
` });
await page.evaluate(() => {
  const card = document.createElement('div');
  card.id = 'card';
  card.innerHTML = '<h2>Los Angeles buildings and parcels</h2>' +
    '<p>Every lot and building in LA County, shaded by its area.</p>' +
    '<div class="by">la.stamen.com · Stamen Design</div>';
  document.body.appendChild(card);
});
await page.evaluate(() => document.fonts.ready);
await page.waitForFunction(() => window.__map?.loaded() && window.__map.areTilesLoaded(), null, { timeout: 90000 });
await page.waitForTimeout(800);
const out = path.join(root, 'social.jpg');
await page.screenshot({ path: out, type: 'jpeg', quality: 85 });
await browser.close();
console.log(`wrote ${out}`);
