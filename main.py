from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime, timezone
import random

app = FastAPI(title="MacroPulse AI API", version="0.1.0")

# Serve frontend folder
app.mount("/static", StaticFiles(directory="../frontend", html=True), name="static")

# ---------- Mock "live" market engine ----------
ASSETS = {
    "SPY": {"name": "S&P 500 (SPY)", "price": 500.00},
    "GLD": {"name": "Gold (GLD)", "price": 190.00},
    "BTC": {"name": "Bitcoin (BTC-USD)", "price": 50000.00},
    "TLT": {"name": "Treasuries (TLT)", "price": 95.00},
}

def _tick_price(p: float, vol: float) -> float:
    # small random walk
    shock = random.gauss(0, vol)
    return max(0.01, p * (1 + shock))

def _pct(new: float, old: float) -> float:
    # (new-old)/old * 100
    if old == 0:
        return 0.0
    return (new - old) / old * 100.0

def _regime(spy_ret: float, btc_ret: float, tlt_ret: float, gld_ret: float) -> tuple[str, float]:
    """
    Simple regime label:
      Risk-On: SPY & BTC up, Treasuries down
      Risk-Off: Treasuries & Gold up, SPY down
      Transition: everything else
    Confidence is a rough score based on how clean the pattern is.
    """
    risk_on = (spy_ret > 0 and btc_ret > 0 and tlt_ret < 0)
    risk_off = (tlt_ret > 0 and gld_ret > 0 and spy_ret < 0)

    if risk_on:
        conf = min(0.95, 0.55 + 0.08 * (abs(spy_ret) + abs(btc_ret) + abs(tlt_ret)))
        return "RISK-ON", conf
    if risk_off:
        conf = min(0.95, 0.55 + 0.08 * (abs(tlt_ret) + abs(gld_ret) + abs(spy_ret)))
        return "RISK-OFF", conf

    conf = 0.45 + 0.04 * (abs(spy_ret) + abs(btc_ret))
    return "TRANSITION", min(0.75, conf)

def _signal(asset: str, ret_1h: float, vol_spike: bool, regime: str) -> dict:
    """
    Demo signal logic (replace with ML later).
    Produces BUY/SELL/HOLD + confidence + drivers.
    """
    # Base probability from momentum (demo)
    p_up = 0.50 + 0.06 * max(-5, min(5, ret_1h))  # clamp

    if regime == "RISK-ON" and asset in ("SPY", "BTC"):
        p_up += 0.08
    if regime == "RISK-OFF" and asset in ("GLD", "TLT"):
        p_up += 0.08
    if vol_spike:
        p_up -= 0.05  # uncertainty penalty

    p_up = max(0.05, min(0.95, p_up))
    if p_up >= 0.60:
        action = "BUY"
    elif p_up <= 0.40:
        action = "SELL"
    else:
        action = "HOLD"

    drivers = []
    drivers.append(f"1-tick momentum: {ret_1h:+.2f}%")
    drivers.append(f"regime: {regime}")
    if vol_spike:
        drivers.append("volatility spike: caution")

    return {
        "asset": asset,
        "action": action,
        "confidence": round(p_up * 100, 1),
        "drivers": drivers[:2],
    }

# keep last prices in memory (for demo)
_last = {k: v["price"] for k, v in ASSETS.items()}

class LiveResponse(BaseModel):
    ts_utc: str
    assets: dict
    detector: dict
    regime: dict
    signals: list

@app.get("/", response_class=HTMLResponse)
def root():
    # Serve the static index.html
    with open("../frontend/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/live", response_model=LiveResponse)
def live():
    global _last

    # simulate updates
    new_prices = {}
    vols = {"SPY": 0.0009, "GLD": 0.0007, "BTC": 0.0025, "TLT": 0.0010}

    # generate mock volume + vol spike flags
    volume = {}
    vol_spike = {}
    for a in ASSETS:
        new_prices[a] = _tick_price(_last[a], vols[a])
        volume[a] = int(1_000_000 * (1 + abs(random.gauss(0, 0.6))))
        vol_spike[a] = random.random() < 0.12  # 12% chance spike flag

    # compute short-horizon % changes
    rets = {a: _pct(new_prices[a], _last[a]) for a in ASSETS}

    # detector panel metrics
    rs_rank = sorted(rets.items(), key=lambda x: x[1], reverse=True)
    leader = rs_rank[0][0]
    laggard = rs_rank[-1][0]

    regime_label, regime_conf = _regime(rets["SPY"], rets["BTC"], rets["TLT"], rets["GLD"])

    # signals
    signals = [
        _signal("SPY", rets["SPY"], vol_spike["SPY"], regime_label),
        _signal("GLD", rets["GLD"], vol_spike["GLD"], regime_label),
        _signal("BTC", rets["BTC"], vol_spike["BTC"], regime_label),
        _signal("TLT", rets["TLT"], vol_spike["TLT"], regime_label),
    ]

    # update last
    _last = new_prices

    return {
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "assets": {
            a: {
                "name": ASSETS[a]["name"],
                "price": round(new_prices[a], 2),
                "chg_pct": round(rets[a], 3),
                "volume": volume[a],
                "vol_spike": vol_spike[a],
            } for a in ASSETS
        },
        "detector": {
            "leader": leader,
            "laggard": laggard,
            "relative_strength_rank": [{"asset": k, "chg_pct": round(v, 3)} for k, v in rs_rank],
        },
        "regime": {"label": regime_label, "confidence": round(regime_conf * 100, 1)},
        "signals": signals,
    }
