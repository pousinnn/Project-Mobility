"""Multi-agent grid simulation (Python) + WebGL viewer.
Run:  python server.py [Settings.yaml]   then open http://localhost:8000
"""
import json, os, random, re, sys, threading, time, webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 8000

def load_settings(path):
    txt = open(path, encoding="utf-8").read()
    try:
        import yaml
        s = yaml.safe_load(txt)
        if isinstance(s, dict): return s
    except Exception:
        pass
    # tolerant fallback (no PyYAML, or JSON-like text with missing commas)
    txt = re.sub(r"#.*", "", txt)
    s = {}
    for k, v in re.findall(r'"?(\w+)"?\s*:\s*(\[[^\]]*\]|"[^"]*"|[\d.]+)', txt):
        s[k] = json.loads(v)
    return s

class Sim:
    def __init__(self, cfg):
        self.cfg = cfg
        self.W, self.H = cfg["GridSize"]
        self.speed = {"A": float(cfg["A_speed"]), "B": float(cfg["B_speed"])}
        self.t_hold = float(cfg["t_hold"]); self.t_new = float(cfg["t_new"])
        self.agents, self.next_id, self.lock = {}, 1, threading.Lock()
        now = time.time()
        for t in "ABC":
            for _ in range(int(cfg["N" + t])): self.spawn(t, now)
        self.next_c = now + self.t_new

    def rand_cell(self): return random.randrange(self.W), random.randrange(self.H)

    def spawn(self, t, now, log=True):
        x, y = self.rand_cell()
        a = dict(id=self.next_id, t=t, x=x, y=y, tx=x, ty=y, moving=False,
                 t0=0, dur=1, next_move=now + random.random() * self.t_hold, count=0)
        self.agents[self.next_id] = a; self.next_id += 1
        if log: print(f"  + new {t}#{a['id']} at ({x},{y})")
        return a

    def at(self, t, x, y):
        return [a for a in self.agents.values() if a["t"] == t and a["x"] == x and a["y"] == y]

    def remove(self, a): self.agents.pop(a["id"], None)

    def resolve(self, a, now):
        """a has just settled in cell (x,y): apply the interaction rules."""
        x, y = a["x"], a["y"]
        if a["t"] == "A":
            for b in self.at("B", x, y):
                print(f"  A#{a['id']} meets B#{b['id']} at ({x},{y}) -> B disappears")
                self.remove(b); a["count"] += 1
                if a["count"] % 3 == 0:
                    print(f"  A#{a['id']} met B 3 times -> new A"); self.spawn("A", now)
        elif a["t"] == "B":
            if self.at("A", x, y):
                A = self.at("A", x, y)[0]
                print(f"  B#{a['id']} meets A#{A['id']} at ({x},{y}) -> B disappears")
                self.remove(a); A["count"] += 1
                if A["count"] % 3 == 0:
                    print(f"  A#{A['id']} met B 3 times -> new A"); self.spawn("A", now)
                return
            for c in self.at("C", x, y):
                print(f"  B#{a['id']} meets C#{c['id']} at ({x},{y}) -> C disappears")
                self.remove(c); a["count"] += 1
                if a["count"] % 2 == 0:
                    print(f"  B#{a['id']} visited C 2 times -> new B"); self.spawn("B", now)

    def step(self, now):
        with self.lock:
            if now >= self.next_c:
                self.spawn("C", now); self.next_c += self.t_new
            for a in list(self.agents.values()):
                if a["t"] == "C" or a["id"] not in self.agents: continue
                if a["moving"]:
                    if now >= a["t0"] + a["dur"]:
                        a["x"], a["y"], a["moving"] = a["tx"], a["ty"], False
                        a["next_move"] = now + self.t_hold
                        self.resolve(a, now)
                elif now >= a["next_move"]:
                    opts = [(a["x"] + dx, a["y"] + dy) for dx, dy in ((1,0),(-1,0),(0,1),(0,-1))
                            if 0 <= a["x"] + dx < self.W and 0 <= a["y"] + dy < self.H]
                    a["tx"], a["ty"] = random.choice(opts)
                    a["moving"], a["t0"], a["dur"] = True, now, 1.0 / self.speed[a["t"]]

    def snapshot(self, now):
        with self.lock:
            out = []
            for a in self.agents.values():
                x, y = a["x"], a["y"]
                if a["moving"]:
                    p = min(1.0, (now - a["t0"]) / a["dur"])
                    x += (a["tx"] - x) * p; y += (a["ty"] - y) * p
                out.append({"id": a["id"], "t": a["t"], "x": round(x, 3), "y": round(y, 3)})
            return out

    def print_locations(self):
        with self.lock:
            print(f"\n[{time.strftime('%H:%M:%S')}] agent locations")
            for t in "ABC":
                items = sorted((a for a in self.agents.values() if a["t"] == t), key=lambda a: a["id"])
                print(f"  {t} ({len(items)}): " + " ".join(f"#{a['id']}@({a['x']},{a['y']})" for a in items))

def main():
    cfg = load_settings(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "Settings.yaml"))
    sim = Sim(cfg)

    def loop():
        last_print = 0
        while True:
            now = time.time(); sim.step(now)
            if now - last_print >= 1.0: sim.print_locations(); last_print = now
            time.sleep(0.02)
    threading.Thread(target=loop, daemon=True).start()

    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
        def log_message(self, *a): pass
        def send_json(self, obj):
            body = json.dumps(obj).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
        def do_GET(self):
            if self.path == "/": self.path = "/web/index.html"
            if self.path == "/config":
                return self.send_json({"grid": [sim.W, sim.H], "files": {t: cfg[t + "_file"] for t in "ABC"}})
            if self.path.startswith("/state"):
                return self.send_json({"agents": sim.snapshot(time.time())})
            super().do_GET()

    server = ThreadingHTTPServer(("", PORT), H)
    url = f"http://localhost:{PORT}"
    print(f"Serving {url}  (Ctrl+C to stop)")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()  # auto-launch the browser
    server.serve_forever()

if __name__ == "__main__":
    main()
