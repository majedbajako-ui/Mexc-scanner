MEXC Scanner - Android/Web starter

This version uses a small Python server as the bridge to MEXC, avoiding browser CORS problems.
It reads public 24h ticker data only; no API key and no trading.

Run on a computer/VPS:
1) pip install -r requirements.txt
2) python server.py
3) open http://SERVER-IP:8080 on Android.

The score is heuristic, not a prediction. Next upgrade: candle history, volume spike vs average, breakout, acceleration, and alerts.
