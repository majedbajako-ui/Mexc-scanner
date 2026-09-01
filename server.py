from flask import Flask, jsonify, send_from_directory
import requests
import math
import time
import os

app = Flask(__name__, static_folder='.')

MEXC = 'https://api.mexc.com'


def get_klines(symbol):
    try:
        url = f'{MEXC}/api/v1/contract/kline/{symbol}'
        params = {
            'interval': 'Min5',
            'start': int(time.time()) - 13 * 5 * 60,
            'end': int(time.time())
        }

        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        if not data.get('success'):
            return None

        d = data.get('data', {})

        volumes = d.get('vol', [])
        opens = d.get('open', [])
        closes = d.get('close', [])

        if len(volumes) < 2:
            return None

        volumes = [float(v) for v in volumes]
        opens = [float(v) for v in opens]
        closes = [float(v) for v in closes]

        last_volume = volumes[-1]
        previous_volumes = volumes[:-1]

        avg_volume = sum(previous_volumes) / len(previous_volumes)

        if avg_volume <= 0:
            return None

        volume_spike = last_volume / avg_volume

        last_open = opens[-1]
        last_close = closes[-1]

        candle_change = 0

        if last_open > 0:
            candle_change = ((last_close - last_open) / last_open) * 100

        return {
            'volume_spike': volume_spike,
            'candle_change': candle_change
        }

    except Exception:
        return None


def score(x):
    move = abs(x['pct'])

    # حركة 24 ساعة
    move_score = min(move / 3 * 20, 20)

    # حجم التداول
    volume_score = min(
        math.log10(max(x['vol'], 1)) / 10 * 20,
        20
    )

    # Volume Spike
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

    # حركة آخر 5 دقائق
    candle_move = abs(x.get('candle_change', 0))
    candle_score = min(candle_move * 5, 20)

    total = (
        move_score +
        volume_score +
        spike_score +
        candle_score
    )

    return round(min(100, total), 1)


@app.get('/')
def home():
    return send_from_directory('.', 'index.html')


@app.get('/api/scan')
def scan():

    # جلب جميع عقود MEXC Futures
    contracts_response = requests.get(
        f'{MEXC}/api/v1/contract/detail',
        timeout=15
    )

    contracts_response.raise_for_status()

    contracts_data = contracts_response.json()

    if not contracts_data.get('success'):
        return jsonify(
            ok=False,
            error='فشل جلب عقود Futures من MEXC'
        ), 500

    contracts = contracts_data.get('data', [])

    # فقط عقود USDT الدائمة
    futures_symbols = set()

    for c in contracts:

        symbol = c.get('symbol', '')

        quote = c.get('quoteCoin', '')
        future_type = c.get('futureType')

        if (
            quote == 'USDT'
            and future_type == 1
            and symbol
        ):
            futures_symbols.add(symbol)

    # جلب بيانات Futures
    ticker_response = requests.get(
        f'{MEXC}/api/v1/contract/ticker',
        timeout=15
    )

    ticker_response.raise_for_status()

    ticker_data = ticker_response.json()

    if not ticker_data.get('success'):
        return jsonify(
            ok=False,
            error='فشل جلب بيانات Futures'
        ), 500

    tickers = ticker_data.get('data', [])

    out = []

    for x in tickers:

        symbol = x.get('symbol', '')

        # نتأكد أن العملة Futures USDT فعلاً
        if symbol not in futures_symbols:
            continue

        try:

            price = float(x.get('lastPrice', 0))
            pct = float(x.get('riseFallRate', 0)) * 100

            # amount24 = قيمة التداول خلال 24 ساعة
            vol = float(x.get('amount24', 0))

            row = {
                'symbol': symbol,
                'price': price,
                'pct': pct,
                'vol': vol,
                'volume_spike': 0,
                'candle_change': 0
            }

        except Exception:
            continue

        # فحص شموع 5 دقائق
        k = get_klines(symbol)

        if k:

            row['volume_spike'] = round(
                k['volume_spike'], 2
            )

            row['candle_change'] = round(
                k['candle_change'], 3
            )

        row['score'] = score(row)

        out.append(row)

    # ترتيب حسب Score
    out.sort(
        key=lambda z: z['score'],
        reverse=True
    )

    return jsonify(
        ok=True,
        time=int(time.time()),
        rows=out[:50]
    )


# Render PORT
port = int(os.environ.get('PORT', 8080))

app.run(
    host='0.0.0.0',
    port=port
)
