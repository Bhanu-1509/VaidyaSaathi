"""Dev server: serves this folder and proxies /api/<service>/... to the FastAPI services.
Proxying avoids CORS, so the backend needs no changes. Run: python server.py"""
import http.server, urllib.request, urllib.error, os
PORTS = {"auth": 8000, "doctor": 8001, "patient": 8002, "appointment": 8003, "schedule": 8004, "lab": 8006, "ai": 8007}
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class H(http.server.SimpleHTTPRequestHandler):
    def proxy(self):
        parts = self.path.split("/", 3)  # "", "api", svc, rest
        svc = parts[2] if len(parts) > 2 else ""
        rest = parts[3] if len(parts) > 3 else ""
        port = PORTS.get(svc)
        if not port:
            return self.send_error(404)
        base = os.getenv(f"API_{svc.upper()}_URL", f"http://127.0.0.1:{port}")
        n = int(self.headers.get("Content-Length") or 0)
        req = urllib.request.Request(f"{base}/{rest}", data=self.rfile.read(n) if n else None, method=self.command)
        for k in ("Authorization", "Content-Type"):
            if self.headers.get(k):
                req.add_header(k, self.headers[k])
        req.add_header("X-Forwarded-For", self.client_address[0])
        try:
            r = urllib.request.urlopen(req, timeout=90 if svc == "ai" else 20); code, body = r.status, r.read()
        except urllib.error.HTTPError as e:
            code, body = e.code, e.read()
        except Exception:
            code, body = 503, ('{"detail":"The %s service is not running. Start it and try again."}' % svc).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        self.proxy() if self.path.startswith("/api/") else super().do_GET()
    do_POST = do_PATCH = do_PUT = do_DELETE = proxy

    def end_headers(self):
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")  # always load the latest app.js/style.css
        super().end_headers()

print("VaidyaSaathi frontend on http://127.0.0.1:5173")
http.server.ThreadingHTTPServer((os.getenv("BIND", "127.0.0.1"), 5173), H).serve_forever()
