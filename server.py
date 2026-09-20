from flask import Flask, jsonify, send_from_directory
import requests
import time
import os

app = Flask(__name__, static_folder=".")

MEXC = "https://api.mexc.com"


def get_json(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
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

    if not data:
        return 0, 0

    if data.get("success") is False:
        return 0, 0

    k = data.get("data", {})

    if not isinstance(k, dict):
        return 0, 0

    try:
        volumes = [float(x) for x in k.get("vol", [])]
        opens = [float(x) for x in k.get("open", [])]
        closes = [float(x) for x in k.get("close", [])]

        if len(volumes) < 3:
            return 0, 0

        if len(opens) < 1 or len(closes) < 1:
            return 0, 0

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

    move = abs(row["pct"])

    if move >= 15:
        score += 20
    elif move >= 10:
        score += 16
    elif move >= 7:
        score += 12
    elif move >= 5:
        score += 8
    elif move >= 3:
        score += 5
    elif move >= 1.5:
        score += 2

    spike = row["volume_spike"]

    if spike >= 8:
        score += 40
    elif spike >= 5:
        score += 35
    elif spike >= 3:
        score += 28
    elif spike >= 2:
        score += 20
    elif spike >= 1.5:
        score += 12
    elif spike >= 1.2:
        score += 6

    candle = abs(row["candle_change"])

    if candle >= 5:
        score += 40
    elif candle >= 3:
        score += 32
    elif candle >= 2:
        score += 24
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

    contracts = get_json(
        f"{MEXC}/api/v1/contract/detail"
    )

    if not contracts:
        return jsonify(
            ok=False,
            error="MEXC Futures contracts error"
        ), 500

    futures = set()

    for contract in contracts.get("data", []):

        if (
            contract.get("quoteCoin") == "USDT"
            and contract.get("state") == 0
        ):
            symbol = contract.get("symbol")

            if symbol:
                futures.add(symbol)

    if not futures:
        return jsonify(
            ok=False,
            error="No USDT Futures contracts found"
        ), 500

    tickers = get_json(
        f"{MEXC}/api/v1/contract/ticker"
    )

    if not tickers:
        return jsonify(
            ok=False,
            error="MEXC Futures ticker error"
        ), 500

    ticker_data = tickers.get("data", [])

    if isinstance(ticker_data, dict):
        ticker_data = [ticker_data]

    rows = []

    for ticker in ticker_data:

        symbol = ticker.get("symbol", "")

        if symbol not in futures:
            continue

        try:
            price = float(
                ticker.get("lastPrice", 0)
            )

            pct = float(
                ticker.get("riseFallRate", 0)
            ) * 100

            volume = float(
                ticker.get("amount24", 0)
            )

            rows.append({
                "symbol": symbol,
                "price": price,
                "pct": pct,
                "vol": volume,
                "volume_spike": 0,
                "candle_change": 0,
                "score": 0
            })

        except Exception:
            continue

    if not rows:
        return jsonify(
            ok=False,
            error="No Futures ticker data found"
        ), 500

    rows.sort(
        key=lambda x: (
            abs(x["pct"]),
            x["vol"]
        ),
        reverse=True
    )

    candidates = rows[:30]

    for row in candidates:

        spike, candle = get_volume_spike(
            row["symbol"]
        )

        row["volume_spike"] = spike
        row["candle_change"] = candle

        row["score"] = calculate_score(row)

    for row in rows[30:100]:

        row["score"] = calculate_score(row)

    result = rows[:100]

    result.sort(
        key=lambda x: (
            x["score"],
            abs(x["pct"]),
            x["volume_spike"]
        ),
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
