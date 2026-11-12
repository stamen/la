// Screenshot the viewer at given views without a web server.
//
//   node screenshot.mjs OUT_DIR "z/lat/lon" ["z/lat/lon" ...]
//
// Env:
//   TILES_DIR   directory holding la-raster.pmtiles / la-vector.pmtiles (default ../data)
//   DEPS_DIR    node_modules with maplibre-gl, pmtiles, fflate; when set, unpkg.com
//               requests are answered from there (for offline/sandboxed runs)
//   SCALE       deviceScaleFactor (default 1)
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');  // repo root: the site's index.html
// Resolve playwright locally, falling back to the global install.
const require = createRequire(import.meta.url);
let pw;
try { pw = require('playwright'); } catch { pw = require(path.join(execSync('npm root -g').toString().trim(), 'playwright')); }
const { chromium } = pw;
const [outDir, ...views] = process.argv.slice(2);
const tilesDir = process.env.TILES_DIR || path.join(here, 'prototype', 'data');
const depsDir = process.env.DEPS_DIR;
const ORIGIN = 'http://la.test/';

const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css' };

function serveFile(route, file, headers) {
  if (!fs.existsSync(file)) return route.fulfill({ status: 404, body: 'not found' });
  const size = fs.statSync(file).size;
  const range = /bytes=(\d+)-(\d*)/.exec(headers.range || '');
  const type = types[path.extname(file)] || 'application/octet-stream';
  if (!range) return route.fulfill({ status: 200, body: fs.readFileSync(file), contentType: type });
  const start = +range[1];
  const end = range[2] ? Math.min(+range[2], size - 1) : size - 1;
  const buf = Buffer.alloc(end - start + 1);
  const fd = fs.openSync(file, 'r');
  fs.readSync(fd, buf, 0, buf.length, start);
  fs.closeSync(fd);
  return route.fulfill({
    status: 206, body: buf, contentType: type,
    headers: { 'content-range': `bytes ${start}-${end}/${size}`, 'accept-ranges': 'bytes' },
  });
}

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 1200, height: 800 }, deviceScaleFactor: +(process.env.SCALE || 1) });
page.on('console', (m) => { if (m.type() === 'error') console.error('console:', m.text()); });
page.on('pageerror', (e) => console.error('pageerror:', e.message));

await page.route('**/*', (route) => {
  const url = new URL(route.request().url());
  const headers = route.request().headers();
  if (url.origin + '/' === ORIGIN) {
    const p = decodeURIComponent(url.pathname);
    if (p.startsWith('/tiles/')) return serveFile(route, path.join(tilesDir, p.slice(7)), headers);
    return serveFile(route, path.join(here, p === '/' ? 'index.html' : p.slice(1)), headers);
  }
  if (depsDir && url.hostname === 'unpkg.com') {
    // /maplibre-gl@6.13.0/dist/x -> DEPS_DIR/maplibre-gl/dist/x
    const m = /^\/(@?[^@/]+(?:\/[^@/]+)?)@[^/]+\/(.*)$/.exec(url.pathname);
    if (m) return serveFile(route, path.join(depsDir, m[1], m[2]), headers);
  }
  return route.abort();
});

fs.mkdirSync(outDir, { recursive: true });
for (const view of views) {
  const [z, lat, lon] = view.split('/');
  await page.goto(`${ORIGIN}index.html${process.env.QUERY || ''}#${z}/${lat}/${lon}`);
  await page.waitForFunction(() => window.__map && window.__map.loaded() && window.__map.areTilesLoaded(), null, { timeout: 120000 })
    .catch(() => console.error(`timeout waiting for tiles at ${view}`));
  await page.waitForTimeout(500);
  const file = path.join(outDir, `view_z${z}_${lat}_${lon}.png`);
  await page.screenshot({ path: file });
  console.log('wrote', file);
}
await browser.close();
