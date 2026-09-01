from flask import Flask, jsonify, send_from_directory
import requests, math, time
app=Flask(__name__, static_folder='.')

def score(x):
    move=abs(x['pct'])
    # Heuristic only: 24h move + quote volume. Not a prediction.
    return round(min(100, min(move/3*50,50)+min(math.log10(max(x['vol'],1))/10*30,30)+min(move/1.5*20,20)),1)

@app.get('/')
def home(): return send_from_directory('.', 'index.html')
@app.get('/api/scan')
def scan():
    r=requests.get('https://api.mexc.com/api/v3/ticker/24hr',timeout=15); r.raise_for_status()
    out=[]
    for x in r.json():
        s=x.get('symbol','')
        if not s.endswith('USDT'): continue
        try:
            row={'symbol':s,'price':float(x['lastPrice']),'pct':float(x['priceChangePercent']),'vol':float(x['quoteVolume'])}
        except: continue
        row['score']=score(row); out.append(row)
    out.sort(key=lambda z:z['score'],reverse=True)
    return jsonify(ok=True,time=int(time.time()),rows=out[:20])
app.run(host='0.0.0.0',port=8080)
