// Placeholder HTTP server for the Lovable preview pane.
// This repo is a Python Telegram bot — run it with: python main.py
const http = require('http');

const args = process.argv.slice(2);
let port = parseInt(process.env.PORT || '8080', 10);
const i = args.indexOf('--port');
if (i !== -1 && args[i + 1]) port = parseInt(args[i + 1], 10);

const html = `<!doctype html>
<html><head><meta charset="utf-8"><title>JEE Forum Bot</title>
<style>
  body{font-family:system-ui,sans-serif;background:#0b1020;color:#e6e9ef;
       display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
  .card{max-width:560px;padding:32px;border:1px solid #2a3358;border-radius:14px;background:#121833}
  h1{margin:0 0 12px;font-size:22px}
  code{background:#0b1020;padding:2px 6px;border-radius:4px}
  a{color:#7aa2ff}
</style></head>
<body><div class="card">
  <h1>🤖 JEE Forum Management Bot</h1>
  <p>This repository is a <strong>Python Telegram bot</strong>, not a web app.</p>
  <p>Run locally:</p>
  <pre><code>pip install -r requirements.txt
python main.py</code></pre>
  <p>See <a href="README.md">README.md</a> for BotFather + Railway setup.</p>
</div></body></html>`;

http.createServer((_, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(html);
}).listen(port, '0.0.0.0', () => console.log('Placeholder preview on :' + port));
