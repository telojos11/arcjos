#!/usr/bin/env python3
# Serves origin A (127.0.0.1:8080) and origin B (localhost:8081) from one process.
import http.server, socketserver, threading, os, functools
BASE = os.path.dirname(os.path.abspath(__file__))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
def serve(port):
    socketserver.TCPServer.allow_reuse_address = True
    h = functools.partial(Q, directory=BASE)
    with socketserver.TCPServer(('127.0.0.1', port), h) as s: s.serve_forever()
for p in (9080, 9081):
    threading.Thread(target=serve, args=(p,), daemon=True).start()
print('Attacker origin (127.0.0.1:9080):  http://127.0.0.1:9080/503614310-harness.html')
print('Automated probe (no interaction): http://127.0.0.1:9080/503614310-automated.html')
print('Victim origin  (localhost:9081):   http://localhost:9081/503614310-harness.html')
threading.Event().wait()
