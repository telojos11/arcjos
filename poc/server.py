#!/usr/bin/env python3
"""Storage Access Permissions-Policy bypass — PoC Server"""
import http.server, socketserver, os, functools, json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    
    def do_GET(self):
        # Send Permissions-Policy: storage-access=() on all responses
        self.send_response(200)
        self.send_header('Permissions-Policy', 'storage-access=()')
        self.send_header('Access-Control-Allow-Origin', '*')
        
        if self.path == '/':
            self.path = '/index.html'
        
        # Serve static files
        path = self.translate_path(self.path)
        if os.path.exists(path) and not os.path.isdir(path):
            ext = os.path.splitext(path)[1]
            ct = {'html': 'text/html', 'js': 'text/javascript', 'json': 'application/json'}.get(ext[1:], 'text/plain')
            self.send_header('Content-Type', ct + '; charset=utf-8')
            self.end_headers()
            with open(path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'path': self.path}).encode())

def serve(port):
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('127.0.0.1', port), functools.partial(H, directory=BASE)) as s:
        s.serve_forever()

import threading
for p in (9080, 9081):
    threading.Thread(target=serve, args=(p,), daemon=True).start()

print('Main page:  http://127.0.0.1:9080/')
print('Iframe:     http://localhost:9081/iframe.html')
print('Policy:     Permissions-Policy: storage-access=()')
threading.Event().wait()
