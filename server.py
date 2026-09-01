from flask import Flask, jsonify, send_from_directory
import requests
import time
import os

app = Flask(__name__, static_folder=".")

MEXC = "https://api.mexc.com"


def get_json(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def get_volume_spike(symbol):
    data = get_json(
        f"{MEXC}/api/v1/contract/kline/{symbol}",
        {
            "interval": "Min5",
            "limit": 13
        }
    )

    if not data or not data.get("success"):
        return 0, 0

    k = data.get("data", {})

    try:
        volumes = [float(x) for x in k.get("vol", [])]
        opens = [float(x) for x in k.get("open", [])]
        closes = [float(x) for x in k.get("close", [])]

        if len(volumes) < 3 or len(opens) < 1 or len(closes) < 1:
            return 0, 0

        # آخر شمعة مقارنة بمتوسط الشموع السابقة
        previous = volumes[:-1]
        avg_volume = sum(previous) / len(previous)

        if avg_volume <= 0:
            return 0, 0

        spike = volumes[-1] / avg_volume

        candle_change = 0

        if opens[-1] > 0:
            candle_change = (
                (closes[-1] - opens[-1])
                / opens[-1]
            ) * 100

        return round(spike, 2), round(candle_change, 3)

    except Exception:
        return 0, 0


def calculate_score(row):
    score = 0

    # حركة 24 ساعة
    move = abs(row["pct"])

    if move >= 10:
        score += 20
    elif move >= 5:
        score += 15
    elif move >= 3:
        score += 10
    elif move >= 1.5:
        score += 5

    # Volume Spike
    spike = row["volume_spike"]

    if spike >= 5:
        score += 50
    elif spike >= 3:
        score += 40
    elif spike >= 2:
        score += 30
    elif spike >= 1.5:
        score += 20
    elif spike >= 1.2:
        score += 10

    # حركة شمعة 5 دقائق
    candle = abs(row["candle_change"])

    if candle >= 3:
        score += 30
    elif candle >= 2:
        score += 25
    elif candle >= 1:
        score += 15
    elif candle >= 0.5:
        score += 8

    return min(score, 100)


@app.get("/")
def home():
    return send_from_directory(".", "index.html")


@app.get("/api/scan")
def scan():

    # 1 — عقود Futures
    contracts = get_json(
        f"{MEXC}/api/v1/contract/detail"
    )

    if not contracts or not contracts.get("success"):
        return jsonify(
            ok=False,
            error="MEXC Futures contracts error"
        ), 500

    futures = set()

    for c in contracts.get("data", []):
        if (
            c.get("quoteCoin") == "USDT"
            and c.get("futureType") == 1
            and c.get("state") == 0
        ):
            futures.add(c.get("symbol"))

    # 2 — Futures ticker
    tickers = get_json(
        f"{MEXC}/api/v1/contract/ticker"
    )

    if not tickers or not tickers.get("success"):
        return jsonify(
            ok=False,
            error="MEXC Futures ticker error"
        ), 500

    rows = []

    for x in tickers.get("data", []):

        symbol = x.get("symbol", "")

        # فقط Futures USDT
        if symbol not in futures:
            continue

        try:
            rows.append({
                "symbol": symbol,
                "price": float(x.get("lastPrice", 0)),
                "pct": float(x.get("riseFallRate", 0)) * 100,
                "vol": float(x.get("amount24", 0)),
                "volume_spike": 0,
                "candle_change": 0,
                "score": 0
            })

        except Exception:
            continue

    # نختار أعلى 10 من ناحية السيولة فقط
    # حتى ما نضغط Render
    rows.sort(
        key=lambda x: x["vol"],
        reverse=True
    )

    candidates = rows[:10]

    # فحص Volume Spike فقط للـ10 المرشحين
    for row in candidates:

        spike, candle = get_volume_spike(
            row["symbol"]
        )

        row["volume_spike"] = spike
        row["candle_change"] = candle

        row["score"] = calculate_score(row)

    # باقي العملات تأخذ Score أساسي
    for row in rows[10:50]:
        row["score"] = calculate_score(row)

    result = rows[:50]

    # ترتيب حسب Score
    result.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return jsonify(
        ok=True,
        time=int(time.time()),
        rows=result
    )


port = int(
    os.environ.get("PORT", 8080)
)

app.run(
    host="0.0.0.0",
    port=port
)
