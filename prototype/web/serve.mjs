// Minimal static server with HTTP Range support (PMTiles needs it).
//
//   node serve.mjs [port]        serves the repo root (the site), and /tiles/* from prototype/data
//
// Env: TILES_DIR overrides where the .pmtiles files are read from.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');  // repo root: the site's index.html
const tilesDir = path.resolve(process.env.TILES_DIR || path.join(here, 'prototype', 'data'));
const port = +(process.argv[2] || 8080);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css' };

function resolve(urlPath) {
  const p = decodeURIComponent(urlPath.split('?')[0]);
  const [root, rel] = p.startsWith('/tiles/') ? [tilesDir, p.slice(7)] : [here, p === '/' ? 'index.html' : p.slice(1)];
  const file = path.resolve(root, rel);
  return file.startsWith(root + path.sep) ? file : null; // no escaping the root
}

http.createServer((req, res) => {
  const file = resolve(req.url);
  if (!file || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404).end('not found');
    return;
  }
  const size = fs.statSync(file).size;
  const headers = {
    'content-type': types[path.extname(file)] || 'application/octet-stream',
    'accept-ranges': 'bytes',
    'access-control-allow-origin': '*',
  };
  const m = /bytes=(\d+)-(\d*)/.exec(req.headers.range || '');
  if (m) {
    const start = +m[1];
    const end = m[2] ? Math.min(+m[2], size - 1) : size - 1;
    res.writeHead(206, { ...headers, 'content-range': `bytes ${start}-${end}/${size}`, 'content-length': end - start + 1 });
    fs.createReadStream(file, { start, end }).pipe(res);
  } else {
    res.writeHead(200, { ...headers, 'content-length': size });
    fs.createReadStream(file).pipe(res);
  }
}).listen(port, () => console.log(`serving ${here} (tiles from ${tilesDir}) on http://localhost:${port}/`));
