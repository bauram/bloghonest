#!/usr/bin/env python3
"""Servidor de desenvolupament amb recàrrega en viu.

    python3 dev.py            → http://localhost:4747 (s'obre sol al navegador)
    python3 dev.py 5050       → un altre port (si està ocupat, prova el següent)

Vigila ../Blog-DS/*.md, build.py i content.py. Quan canvia qualsevol cosa,
regenera dist/ i el navegador es recarrega tot sol (també la pàgina on siguis).
Atura'l amb Ctrl+C.
"""
import glob, importlib, os, sys, threading, time, traceback, webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
import content, build  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4747
DIST = os.path.join(HERE, "dist")
state = {"v": 0, "err": ""}

RELOAD = b"""<script>(function(){var v=null;function tick(){fetch('/__v',{cache:'no-store'}).then(function(r){return r.text()})
.then(function(t){if(v===null)v=t;else if(t!==v){sessionStorage.setItem('__y',scrollY);location.reload();}}).catch(function(){})
.finally(function(){setTimeout(tick,700)});}var y=sessionStorage.getItem('__y');if(y!==null){sessionStorage.removeItem('__y');
addEventListener('load',function(){scrollTo(0,+y)});}tick();})();</script>"""

def watched():
    files = glob.glob(os.path.join(build.SRC, "*.md")) + [os.path.join(HERE, "build.py"), os.path.join(HERE, "content.py")]
    out = {}
    for f in files:
        try: out[f] = os.stat(f).st_mtime
        except OSError: pass
    return out

def rebuild(why=""):
    try:
        importlib.reload(content); importlib.reload(build)
        build.build_static(build.load())
        state["err"] = ""
        print(time.strftime("%H:%M:%S"), "✓ regenerat", why)
    except Exception:
        state["err"] = traceback.format_exc()
        print(time.strftime("%H:%M:%S"), "✗ error\n" + state["err"])
    state["v"] += 1

def watch():
    last = watched()
    while True:
        time.sleep(0.4)
        now = watched()
        if now != last:
            changed = [os.path.basename(f) for f in set(now) | set(last) if now.get(f) != last.get(f)]
            last = now
            time.sleep(0.15)  # deixa acabar l'escriptura
            rebuild("(" + ", ".join(sorted(changed))[:80] + ")")

class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DIST, **k)
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
    def do_GET(self):
        path = self.path.split("?")[0].split("#")[0]
        if path == "/__v":
            b = str(state["v"]).encode()
            self.send_response(200); self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        if path.endswith("/"): path += "index.html"
        f = os.path.normpath(os.path.join(DIST, path.lstrip("/")))
        if not f.startswith(DIST): return self.send_error(403)
        code = 200
        if not os.path.isfile(f):
            f, code = os.path.join(DIST, "404.html"), 404
        if f.endswith(".html") and os.path.isfile(f):
            b = open(f, "rb").read()
            if state["err"]:
                err = ("<pre style='position:fixed;inset:auto 0 0 0;max-height:45vh;overflow:auto;margin:0;padding:16px;"
                       "background:#c23b2e;color:#fff;font:12px/1.4 monospace;z-index:99'>" +
                       state["err"].replace("&", "&amp;").replace("<", "&lt;") + "</pre>").encode()
                b = b.replace(b"</body>", err + b"</body>")
            b = b.replace(b"</body>", RELOAD + b"</body>")
            self.send_response(code); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        return super().do_GET()

if __name__ == "__main__":
    rebuild("(inici)")
    threading.Thread(target=watch, daemon=True).start()
    for p in range(PORT, PORT + 20):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), H); PORT = p; break
        except OSError:
            print(f"  El port {p} està ocupat, provo el següent…")
    else:
        sys.exit("  No he trobat cap port lliure.")
    url = f"http://localhost:{PORT}/"
    print(f"\n  Blog de disseny social → {url}\n  Vigilant canvis a Blog-DS/, build.py i content.py. Ctrl+C per aturar.\n")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\n  Aturat.")
