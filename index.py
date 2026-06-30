# app.py  —  Self-contained trading journal (FastAPI + SQLite + embedded UI)
# Run:  pip install fastapi "uvicorn[standard]"   then   python app.py
# Open: http://localhost:8000

import sqlite3, json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, getcontext
from contextlib import closing
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

getcontext().prec = 28
DB = "journal.db"

# ───────────────────────── Database ─────────────────────────
def init_db():
    with closing(sqlite3.connect(DB)) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS executions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL, side TEXT NOT NULL,
            price TEXT NOT NULL, quantity TEXT NOT NULL,
            executed_at TEXT NOT NULL,
            commission TEXT DEFAULT '0', fees TEXT DEFAULT '0');
        """)
        c.commit()

# ───────────────────── FIFO position engine ─────────────────
@dataclass
class _Lot:
    qty: Decimal; price: Decimal; opened_at: str

@dataclass
class Position:
    symbol: str; direction: str; open_time: str
    close_time: str = None
    total_quantity: Decimal = Decimal("0")
    gross_pnl: Decimal = Decimal("0")
    net_pnl: Decimal = Decimal("0")
    fees_total: Decimal = Decimal("0")
    status: str = "OPEN"; win_loss: str = None

def build_positions(rows):
    by_symbol = defaultdict(list)
    for r in rows:
        by_symbol[r["symbol"]].append(r)
    out = []
    for symbol, fills in by_symbol.items():
        fills.sort(key=lambda x: x["executed_at"])
        longs, shorts, cur = deque(), deque(), None
        for f in fills:
            qty = Decimal(f["quantity"])
            price = Decimal(f["price"])
            per_unit = (Decimal(f["commission"]) + Decimal(f["fees"])) / qty if qty else Decimal("0")
            while qty > 0:
                opening_long  = f["side"] == "BUY"  and not shorts
                opening_short = f["side"] == "SELL" and not longs
                if opening_long or opening_short:
                    direction = "LONG" if f["side"] == "BUY" else "SHORT"
                    if cur is None or cur.status == "CLOSED":
                        cur = Position(symbol, direction, f["executed_at"]); out.append(cur)
                    (longs if direction == "LONG" else shorts).append(_Lot(qty, price, f["executed_at"]))
                    cur.total_quantity += qty; cur.fees_total += per_unit * qty
                    qty = Decimal("0")
                else:
                    closing_long = f["side"] == "SELL"
                    book = longs if closing_long else shorts
                    lot = book[0]; matched = min(qty, lot.qty)
                    gross = (price - lot.price) * matched if closing_long else (lot.price - price) * matched
                    cur.gross_pnl += gross; cur.fees_total += per_unit * matched
                    lot.qty -= matched; qty -= matched
                    if lot.qty == 0: book.popleft()
                    if not book:
                        cur.close_time = f["executed_at"]
                        cur.net_pnl = cur.gross_pnl - cur.fees_total
                        cur.status = "CLOSED"
                        cur.win_loss = "WIN" if cur.net_pnl > 0 else "LOSS" if cur.net_pnl < 0 else "BREAKEVEN"
                        cur = None
    return out

def get_executions():
    with closing(sqlite3.connect(DB)) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute("SELECT * FROM executions ORDER BY executed_at")]

def analytics():
    pos = [p for p in build_positions(get_executions()) if p.status == "CLOSED"]
    if not pos:
        return {"net_pnl": 0, "win_rate": 0, "profit_factor": 0, "total": 0,
                "calendar": {}, "positions": []}
    wins = [p for p in pos if p.net_pnl > 0]
    gross_win = sum((p.net_pnl for p in wins), Decimal("0"))
    gross_loss = sum((-p.net_pnl for p in pos if p.net_pnl < 0), Decimal("0"))
    cal = defaultdict(lambda: {"netPnl": 0.0, "tradeCount": 0})
    for p in pos:
        day = p.close_time[:10]
        cal[day]["netPnl"] += float(p.net_pnl); cal[day]["tradeCount"] += 1
    return {
        "net_pnl": float(sum((p.net_pnl for p in pos), Decimal("0"))),
        "win_rate": round(len(wins) / len(pos) * 100, 1),
        "profit_factor": round(float(gross_win / gross_loss), 2) if gross_loss else 0,
        "total": len(pos),
        "calendar": cal,
        "positions": [{"symbol": p.symbol, "direction": p.direction,
                       "netPnl": float(p.net_pnl), "winLoss": p.win_loss,
                       "closeTime": p.close_time} for p in pos],
    }

# ───────────────────────── API ─────────────────────────
app = FastAPI()

@app.post("/api/executions")
async def add_exec(req: Request):
    b = await req.json()
    with closing(sqlite3.connect(DB)) as c:
        c.execute("""INSERT INTO executions(symbol,side,price,quantity,executed_at,commission,fees)
                     VALUES(?,?,?,?,?,?,?)""",
                  (b["symbol"], b["side"], str(b["price"]), str(b["quantity"]),
                   b["executed_at"], str(b.get("commission", 0)), str(b.get("fees", 0))))
        c.commit()
    return {"ok": True}

@app.post("/api/seed")
def seed():
    sample = [
        ("AAPL","BUY",185.20,100,"2026-06-01T14:30:00",1,0.5),
        ("AAPL","SELL",188.10,100,"2026-06-01T15:45:00",1,0.5),
        ("TSLA","BUY",240.00,50,"2026-06-02T13:30:00",1,0.5),
        ("TSLA","SELL",235.50,50,"2026-06-02T19:00:00",1,0.5),
        ("NVDA","BUY",118.00,80,"2026-06-03T14:00:00",1,0.5),
        ("NVDA","SELL",124.40,80,"2026-06-03T18:30:00",1,0.5),
    ]
    with closing(sqlite3.connect(DB)) as c:
        for s in sample:
            c.execute("""INSERT INTO executions(symbol,side,price,quantity,executed_at,commission,fees)
                         VALUES(?,?,?,?,?,?,?)""", tuple(str(x) for x in s))
        c.commit()
    return {"ok": True, "added": len(sample)}

@app.get("/api/analytics")
def api_analytics():
    return JSONResponse(analytics())

# ───────────────────────── Embedded UI ─────────────────────────
HTML = """<!doctype html><html><head><meta charset=utf8>
<title>TradeJournal</title><style>
:root{--base:#0B0E11;--surface:#151A21;--border:#222B36;--win:#00C805;--loss:#FF3B30;--ai:#007AFF}
*{box-sizing:border-box;font-family:system-ui,sans-serif}
body{margin:0;background:var(--base);color:#9AA7B4}
.wrap{display:flex}
aside{width:240px;min-height:100vh;border-right:1px solid var(--border);background:#151A2199;padding:20px}
.logo{font-weight:700;color:#fff;font-size:18px}.logo span{color:var(--win)}
nav a{display:block;padding:10px 12px;margin-top:6px;border-radius:8px;color:#6B7785;text-decoration:none}
nav a.active{background:#222B3699;color:#fff}
main{flex:1;padding:24px;max-width:1200px}
h1{color:#fff;font-size:20px}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:16px 0}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px}
.card .l{font-size:11px;text-transform:uppercase;color:#6B7785}
.card .v{font-size:24px;font-weight:600;color:#fff;margin-top:8px;font-variant-numeric:tabular-nums}
.v.win{color:var(--win)}.v.loss{color:var(--loss)}
.grid2{display:grid;grid-template-columns:65% 35%;gap:16px}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;margin-top:16px}
.cal{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}
.day{min-height:60px;border:1px solid var(--border);border-radius:8px;padding:6px;font-size:11px}
.day.win{background:rgba(0,200,5,.1);border-color:rgba(0,200,5,.3)}
.day.loss{background:rgba(255,59,48,.1);border-color:rgba(255,59,48,.3)}
.day .p{font-weight:600;margin-top:6px}.p.win{color:var(--win)}.p.loss{color:var(--loss)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:8px;border-bottom:1px solid var(--border)}
th{color:#6B7785;font-weight:500;font-size:11px;text-transform:uppercase}
td.win{color:var(--win)}td.loss{color:var(--loss)}
button{background:var(--ai);color:#fff;border:0;border-radius:8px;padding:8px 14px;cursor:pointer}
</style></head><body><div class=wrap>
<aside><div class=logo>Trade<span>Journal</span></div>
<nav><a class=active>Dashboard</a><a>Journal</a><a>Backtest</a>
<a style=color:#007AFF>Zella AI</a><a>Prop Firm</a><a>Spaces</a></nav></aside>
<main><h1>Overview</h1>
<button onclick="seed()">Load Sample Trades</button>
<div class=cards id=cards></div>
<div class=grid2><div class=panel><b style=color:#fff>Equity / P&L by Day</b><div class=cal id=cal style=margin-top:12px></div></div>
<div class=panel><b style=color:#fff>Recent Positions</b><div id=tbl style=margin-top:12px></div></div></div>
</main></div><script>
const fmt=n=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(n);
async function seed(){await fetch('/api/seed',{method:'POST'});load()}
async function load(){
 const d=await (await fetch('/api/analytics')).json();
 const np=d.net_pnl;
 cards.innerHTML=[
  ['Net P&L',fmt(np),np>0?'win':np<0?'loss':''],
  ['Win Rate',d.win_rate+'%',''],
  ['Profit Factor',d.profit_factor,''],
  ['Total Trades',d.total,'']
 ].map(c=>`<div class=card><div class=l>${c[0]}</div><div class="v ${c[2]}">${c[1]}</div></div>`).join('');
 cal.innerHTML=Object.entries(d.calendar).map(([day,v])=>{
  const cls=v.netPnl>0?'win':v.netPnl<0?'loss':'';
  return `<div class="day ${cls}"><span>${day.slice(8)}</span><div class="p ${cls}">${fmt(v.netPnl)}</div><div style=color:#6B7785>${v.tradeCount} trades</div></div>`
 }).join('')||'<i style=color:#6B7785>No data — click Load Sample Trades</i>';
 tbl.innerHTML=`<table><tr><th>Symbol</th><th>Side</th><th>Result</th><th>Net P&L</th></tr>`+
  d.positions.map(p=>`<tr><td style=color:#fff>${p.symbol}</td><td>${p.direction}</td><td>${p.winLoss}</td><td class="${p.netPnl>0?'win':'loss'}">${fmt(p.netPnl)}</td></tr>`).join('')+`</table>`;
}
load();
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML

if __name__ == "__main__":
    init_db()
    print("→ http://localhost:8000  (click 'Load Sample Trades')")
    uvicorn.run(app, host="0.0.0.0", port=8000)
