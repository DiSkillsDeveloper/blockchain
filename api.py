import time

import requests

API = "https://mempool.space/testnet4/api"

session = requests.Session()


def get_json(url, tries=6):
    for attempt in range(tries):
        try:
            response = session.get(url, timeout=20)
            if response.status_code != 429 and response.status_code < 500:
                response.raise_for_status()
                return response.json()
        except (requests.ConnectionError, requests.Timeout):
            if attempt == tries - 1:
                raise
        time.sleep(2 ** attempt)
    response.raise_for_status()


def get_balance(address):
    data = get_json(f"{API}/address/{address}")
    chain, mempool = data["chain_stats"], data["mempool_stats"]

    confirmed = chain["funded_txo_sum"] - chain["spent_txo_sum"]
    pending = mempool["funded_txo_sum"] - mempool["spent_txo_sum"]

    return {
        "confirmed": confirmed,
        "pending": pending,
        "total": confirmed + pending,
        "tx_count": chain["tx_count"] + mempool["tx_count"],
    }


def get_utxos(address, confirmed_only=True):
    utxos = get_json(f"{API}/address/{address}/utxo")
    if confirmed_only:
        utxos = [u for u in utxos if u["status"]["confirmed"]]
    return sorted(utxos, key=lambda u: u["value"], reverse=True)


def get_transactions(address):
    return get_json(f"{API}/address/{address}/txs")


def get_fee_rate():
    fees = get_json(f"{API}/v1/fees/recommended")
    return max(fees["halfHourFee"], 1)


def broadcast(raw_hex):
    response = requests.post(f"{API}/tx", data=raw_hex, timeout=20)
    if response.status_code != 200:
        raise RuntimeError(f"Network rejected the transaction: {response.text.strip()}")
    return response.text.strip()


def link(txid):
    return f"https://mempool.space/testnet4/tx/{txid}"
