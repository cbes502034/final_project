// Render 靜態部署：每個本機 JS/CSS 都使用內容版本碼，避免 CDN 混用新舊檔案。
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function inside(parent, child) {
  const relative = path.relative(parent, child);
  return !relative || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative));
}

function build(source, output) {
  source = path.resolve(source);
  output = path.resolve(output);
  if (inside(source, output) || inside(output, source)) throw new Error('來源與輸出目錄不可互相包含');
  fs.mkdirSync(output, { recursive: true });
  fs.cpSync(source, output, { recursive: true });
  let pages = 0;
  function visit(folder) {
    for (const item of fs.readdirSync(folder, { withFileTypes: true })) {
      const file = path.join(folder, item.name);
      if (item.isDirectory()) { visit(file); continue; }
      if (!item.name.endsWith('.html')) continue;
      const html = fs.readFileSync(file, 'utf8').replace(/\b(src|href)="([^"?#]+\.(?:js|css))(?:\?[^"#]*)?"/g,
        (original, attribute, url) => {
          if (/^(?:[a-z]+:|\/\/)/i.test(url)) return original;
          const asset = url.startsWith('/') ? path.resolve(output, '.' + url) : path.resolve(path.dirname(file), url);
          if (!inside(output, asset)) throw new Error('資源超出輸出目錄：' + url);
          const version = crypto.createHash('sha256').update(fs.readFileSync(asset)).digest('hex').slice(0, 16);
          return attribute + '="' + url + '?v=' + version + '"';
        });
      fs.writeFileSync(file, html);
      pages++;
    }
  }
  visit(output);
  return pages;
}

if (require.main === module) {
  const root = path.resolve(__dirname, '..');
  const pages = build(process.argv[2] || path.join(root, 'frontend'), process.argv[3] || path.join(root, 'dist/frontend'));
  console.log('Built ' + pages + ' HTML pages with content-versioned assets.');
}
module.exports = { build };
