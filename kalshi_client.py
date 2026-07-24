#!/usr/bin/env python3
"""
Minimal authenticated Kalshi client. Reads .env (KALSHI_ENV, KALSHI_KEY_ID,
KALSHI_PRIVATE_KEY_PATH). Signing: RSA-PSS-SHA256 over timestamp_ms + METHOD + path.

Read-only by design for now: balance / positions / fills. No order methods until
paper-sim shows edge and you say go.

Run: python3 kalshi_client.py   -> auth self-test (balance + exchange status)
"""
import base64, json, os, time
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

HERE = os.path.dirname(os.path.abspath(__file__))
HOSTS = {'demo': 'https://demo-api.kalshi.co',
         'prod': 'https://api.elections.kalshi.com'}


def load_env(path=None):
    env = {}
    for line in open(path or os.path.join(HERE, '.env')):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


class Kalshi:
    def __init__(self):
        env = load_env()
        self.env_name = env.get('KALSHI_ENV', 'demo').lower()
        self.base = HOSTS[self.env_name] + '/trade-api/v2'
        self.key_id = env['KALSHI_KEY_ID']
        pem_path = env['KALSHI_PRIVATE_KEY_PATH']
        if not os.path.isabs(pem_path):
            pem_path = os.path.join(HERE, pem_path)
        self.key = serialization.load_pem_private_key(open(pem_path, 'rb').read(), password=None)

    def _headers(self, method, path):
        ts = str(int(time.time() * 1000))
        msg = (ts + method + '/trade-api/v2' + path).encode()
        sig = self.key.sign(msg, padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                             salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
        return {'KALSHI-ACCESS-KEY': self.key_id,
                'KALSHI-ACCESS-SIGNATURE': base64.b64encode(sig).decode(),
                'KALSHI-ACCESS-TIMESTAMP': ts}

    def get(self, path, **params):
        r = requests.get(self.base + path, headers=self._headers('GET', path.split('?')[0]),
                         params=params or None, timeout=30)
        r.raise_for_status()
        return r.json()

    # -- read-only convenience --
    def balance(self):    return self.get('/portfolio/balance')
    def positions(self):  return self.get('/portfolio/positions')
    def fills(self):      return self.get('/portfolio/fills')


if __name__ == '__main__':
    k = Kalshi()
    print(f"env={k.env_name}  host={k.base}")
    b = k.balance()
    print("AUTH OK  balance:", b)
    pos = k.positions()
    mp = pos.get('market_positions', [])
    print(f"positions: {len(mp)} market position(s)")
    for p in mp[:10]:
        print(f"  {p.get('ticker')}: position={p.get('position')} exposure={p.get('market_exposure')}")
