# MacroPulse AI (Preview)

A clean preview web app (frontend + backend) that simulates a live cross-asset dashboard:
**Gold (GLD), S&P 500 (SPY), Crypto (BTC-USD), Treasuries (TLT)** on one screen with:
- Detector Panel (moves, vol spike flag, volume)
- Simple regime label (Risk-On / Risk-Off / Transition)
- AI Signal preview (BUY/SELL/HOLD) using demo logic

## Run locally
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open: http://127.0.0.1:8000/

## Next steps
- Replace mock feed with real market data (Yahoo Finance + Binance/Coinbase).
- Add real rolling correlations, vol, and an explainable ML model (LogReg/XGBoost).
