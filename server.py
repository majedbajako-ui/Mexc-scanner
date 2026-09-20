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

```
if not data or not data.get("success"):
    return 0, 0

k = data.get("data", {})

try:
    volumes = [float(x) for x in k.get("vol", [])]
    opens = [float(x) for x in k.get("open", [])]
    closes = [float(x) for x in k.get("close", [])]
