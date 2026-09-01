from flask import Flask, jsonify, send_from_directory
import requests
import math
import time
import os

app = Flask(__name__, static_folder='.')

MEXC = 'https://api.mexc.com'


def get_kline(symbol):
    try:
        url = f'{MEXC}/api/v1/contract/kline/{symbol}'
        params = {
            'interval': 'Min5',
            'limit': 13
        }

        r = requests.get(url, params=params, timeout=5)
        data = r.json()

        if not data.get('success'):
            return None

        d = data.get('data', {})

        volumes = d.get('vol', [])
        opens = d.get('open', [])
        closes = d.get('close', [])

        if len(volumes) < 3:
            return None

        volumes = [float(v) for v in volumes]
        opens = [float(v) for v in opens]
        closes = [float(v) for v in closes]

        avg = sum(volumes[:-1]) / len(volumes[:-1])

        if avg <= 0:
            return None

        spike = volumes[-1] / avg

        candle_change = 0

        if opens[-1] > 0:
            candle_change = (
                (closes[-1] - opens[-1])
                / opens[-1]
            ) * 100

        return {
            'volume_spike': round(spike, 2),
            'candle_change': round(candle_change, 3)
        }

    except Exception:
        return None


def score(x):
    move = abs(x['pct'])

    move_score = min(move / 3 * 20, 20)

    volume_score = min(
        math.log10(max(x['vol'], 1)) / 10 * 20,
        20
    )

    spike = x.get('volume_spike', 0)

    if spike >= 5:
        spike_score = 45
    elif spike >= 3:
        spike_score = 38
    elif spike >= 2:
        spike_score = 30
    elif spike >= 1.5:
        spike_score = 20
    elif spike >= 1.2:
        spike_score = 10
    else:
        spike_score = 0

    candle_score = min(
        abs(x.get('candle_change', 0)) * 5,
        20
    )

    return round(
        min(
            100,
            move_score +
            volume_score +
            spike_score +
            candle_score
        ),
        1
    )


@app.get('/')
def home():
    return send_from_directory('.', 'index.html')


@app.get('/api/scan')
def scan():

    # Futures contracts
    contracts = requests.get(
        f'{MEXC}/api/v1/contract/detail',
        timeout=10
    ).json()

    if not contracts.get('success'):
        return jsonify(
            ok=False,
            error='MEXC Futures error'
        ), 500

    futures = {
        c['symbol']
        for c in contracts.get('data', [])
        if c.get('quoteCoin') == 'USDT'
        and c.get('futureType') == 1
    }

    # Futures tickers
    tickers = requests.get(
        f'{MEXC}/api/v1/contract/ticker',
        timeout=10
    ).json()

    if not tickers.get('success'):
        return jsonify(
            ok=False,
            error='MEXC ticker error'
        ), 500

    rows = []

    for x in tickers.get('data', []):

        symbol = x.get('symbol', '')

        if symbol not in futures:
            continue

        try:
            rows.append({
                'symbol': symbol,
                'price': float(x.get('lastPrice', 0)),
                'pct': float(x.get('riseFallRate', 0)) * 100,
                'vol': float(x.get('amount24', 0)),
                'volume_spike': 0,
                'candle_change': 0
            })
        except Exception:
            pass

    # أكبر العملات من حيث التداول
    rows.sort(
        key=lambda x: x['vol'],
        reverse=True
    )

    # نفحص فقط أفضل 10
    candidates = rows[:10]

    for x in candidates:

        k = get_kline(x['symbol'])

        if k:
            x['volume_spike'] = k['volume_spike']
            x['candle_change'] = k['candle_change']

        x['score'] = score(x)

    # الباقي يأخذ Score أساسي
    for x in rows[10:50]:
        x['score'] = score(x)

    result = rows[:50]

    result.sort(
        key=lambda x: x['score'],
        reverse=True
    )

    return jsonify(
        ok=True,
        time=int(time.time()),
        rows=result
    )


port = int(
    os.environ.get('PORT', 8080)
)

app.run(
    host='0.0.0.0',
    port=port
)
