"""PULSE (formerly Spend Coach) - full-stack app. Backend: Python stdlib + SQLite. No pip install needed.
Run:  python app.py   (Windows: py app.py)   then open http://localhost:8000"""
import json, os, sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "spend_coach.db")
PORT = int(os.environ.get("PORT", 8000))
START_BALANCE, TOKENS_PER_CALL, RS_PER_1K = 25000, 150, 0.4

# Merchant map: the ONLY source of categories (unknown merchant => no category, no nudge)
MERCHANTS = {"swiggy": "food", "zomato": "food", "dominos": "food", "starbucks": "food",
             "uber": "travel", "ola": "travel", "rapido": "travel", "irctc": "travel",
             "amazon": "shopping", "myntra": "shopping", "flipkart": "shopping"}
DEFAULT_CAPS = {"food": 3000, "travel": 2000, "shopping": 4000}
SWAPS = {"swiggy": ("Pack a home meal next time", .6), "zomato": ("Try a mess/home meal tonight", .6),
         "dominos": ("Share a medium instead of a large", .4), "starbucks": ("Filter coffee instead", .7),
         "uber": ("Take the metro for this route", .65), "ola": ("Take the metro for this route", .65),
         "rapido": ("Share an auto for short trips", .4), "irctc": ("Book a cheaper class", .3),
         "amazon": ("Wishlist it for 48h first", .3), "myntra": ("Wishlist it for 48h first", .3),
         "flipkart": ("Wishlist it for 48h first", .3)}

# ---------------- Database ----------------
def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init():
    c = db()
    c.execute("""create table if not exists payments(id integer primary key autoincrement, merchant text,
        amount integer, status text, category text, nudge text, saving integer default 0, over integer default 0,
        model_calls integer default 0, action text, reason text, ts text default current_timestamp)""")
    c.execute("create table if not exists caps(category text primary key, cap integer)")
    for k, v in DEFAULT_CAPS.items():
        c.execute("insert or ignore into caps values(?,?)", (k, v))
    c.commit(); c.close()

def get_caps(c): return {r["category"]: r["cap"] for r in c.execute("select * from caps")}

def get_spent(c):
    s = {k: 0 for k in get_caps(c)}
    for r in c.execute("select category, sum(amount) t from payments where category is not null group by category"):
        s[r["category"]] = r["t"]
    return s

# ---------------- Agent: tagger + cap counter + one-line suggester ----------------
def coach(c, key, amount, orig, choice):
    cat = MERCHANTS.get(key)                                   # tagger: map only
    if not cat:
        return dict(nudge=None, reason="Merchant not in map, so no category and no nudge")
    cp, sp = get_caps(c), get_spent(c)
    left = cp[cat] - sp[cat]                                   # cap counter
    text, pct = SWAPS[key]
    if choice in ("swap", "fit", "any"):                       # user answered the over-budget question
        orig = int(orig or amount); over = max(0, orig - left)
        tag = f"Over budget by ₹{over}" if over > 0 else f"Low budget, ₹{left - orig} left"
        msg = {"swap": f'{tag}: chose "{text}", paid ₹{amount} instead of ₹{orig}',
               "fit": f"{tag}: paid only ₹{amount} to stay in cap",
               "any": f"{tag}: chose to pay ₹{orig} in full"}[choice]
        return dict(category=cat, nudge=msg, action="ignore" if choice == "any" else "accept",
                    saving=0 if choice == "any" else orig - amount, over=over, reason="Over budget" if over > 0 else "Low budget")
    rem = left - amount
    if rem >= .25 * cp[cat] and amount < .25 * cp[cat]:
        return dict(category=cat, nudge=None, reason="Well within cap, so no nudge")
    save, over = round(amount * pct), max(0, -rem)             # suggester (template, 0 model calls)
    out = dict(category=cat, saving=save, over=over, reason="Over budget" if over else "Cap nearly used",
               nudge=(f"Over budget by ₹{over}! {cat.title()} cap is ₹{cp[cat]}. {text}, saves ~₹{save}." if over
                      else f"{cat.title()} cap: ₹{max(rem, 0)} left. {text}, saves ~₹{save}."))
    if over:
        room = {k: cp[k] - sp[k] for k in cp if k != cat}
        oth = max(room, key=room.get)
        out["alt"] = dict(text=text, newAmt=amount - save, shiftFrom=oth, shiftAmt=max(0, min(over, room[oth])), cat=cat)
    return out

def pay(c, b):
    merchant, amount = str(b["merchant"]).strip()[:40], int(round(float(b["amount"])))
    if not merchant or amount <= 0: raise ValueError("merchant and positive amount required")
    e = dict(merchant=merchant, amount=amount, status="success", category=None, nudge=None,
             saving=0, over=0, model_calls=0, action=None, reason="", alt=None)
    try:                                                       # payment NEVER depends on the coach
        e.update(coach(c, merchant.lower(), amount, b.get("orig"), b.get("choice")))
    except Exception as x:
        e["reason"] = f"Coach error ignored: {x}"
    cur = c.execute("insert into payments(merchant,amount,status,category,nudge,saving,over,model_calls,action,reason)"
                    " values(?,?,?,?,?,?,?,?,?,?)", (e["merchant"], e["amount"], e["status"], e["category"], e["nudge"],
                    e["saving"], e["over"], e["model_calls"], e["action"], e["reason"]))
    c.commit(); e["id"] = cur.lastrowid
    return e

def state(c):
    log = [dict(r) for r in c.execute("select * from payments order by id")]
    sh = [r for r in log if r["nudge"]]; ac = [r for r in sh if r["action"] == "accept"]
    calls = sum(r["model_calls"] for r in sh); tokens = calls * TOKENS_PER_CALL
    saved = sum(r["saving"] for r in ac); cost = round(tokens / 1000 * RS_PER_1K, 2)
    stats = {"Payments": len(log), "Nudges": len(sh), "Over budget": sum(1 for r in sh if r["over"]),
             "Accepted": len(ac), "Ignored": sum(1 for r in sh if r["action"] == "ignore"),
             "Silent": len(log) - len(sh), "Model calls": calls, "Tokens": tokens, "Saved ₹": saved,
             "Compute ₹": cost, "verdict": "✅ Worth it: savings cover the compute cost" if saved >= cost
             else "⚠️ Nudges cost more than they saved"}
    return dict(caps=get_caps(c), spent=get_spent(c), balance=START_BALANCE - sum(r["amount"] for r in log),
                log=log, stats=stats)

# ---------------- HTTP layer (REST API + static frontend) ----------------
class H(BaseHTTPRequestHandler):
    def send(self, body, code=200, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def handle_api(self, method, body):
        c = db()
        try:
            if method == "GET" and self.path == "/api/state": return self.send(state(c))
            if method == "POST" and self.path == "/api/pay": return self.send(pay(c, body))
            if method == "POST" and self.path == "/api/feedback":
                c.execute("update payments set action=? where id=? and nudge is not null",
                          ("accept" if body["action"] == "accept" else "ignore", int(body["id"]))); c.commit()
                return self.send({"ok": True})
            if method == "POST" and self.path == "/api/caps":
                for k, v in body.items():
                    if k in DEFAULT_CAPS and int(v) > 0: c.execute("update caps set cap=? where category=?", (int(v), k))
                c.commit(); return self.send(get_caps(c))
            if method == "POST" and self.path == "/api/reset":
                c.execute("delete from payments"); c.commit(); return self.send({"ok": True})
            self.send({"error": "not found"}, 404)
        except (KeyError, ValueError, TypeError) as e:
            self.send({"error": str(e)}, 400)
        finally:
            c.close()
    def do_GET(self):
        if self.path.startswith("/api/"): return self.handle_api("GET", {})
        with open(os.path.join(BASE, "static", "index.html"), "rb") as f:
            self.send(f.read(), 200, "text/html")
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError: return self.send({"error": "bad json"}, 400)
        self.handle_api("POST", body)
    def log_message(self, *a): pass

if __name__ == "__main__":
    init()
    print(f"PULSE running -> http://localhost:{PORT}   (Ctrl+C to stop)")
    ThreadingHTTPServer(("", PORT), H).serve_forever()
