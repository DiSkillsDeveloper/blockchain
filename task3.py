import argparse

import api


def btc(sats):
    return f"{sats / 1e8:.8f}"


def show_transactions(address, limit):
    for tx in api.get_transactions(address)[:limit]:
        got = sum(o["value"] for o in tx["vout"]
                  if o.get("scriptpubkey_address") == address)
        spent = sum(i["prevout"]["value"] for i in tx["vin"]
                    if i.get("prevout", {}).get("scriptpubkey_address") == address)

        delta = got - spent
        status = tx["status"]
        where = f"block {status['block_height']}" if status["confirmed"] else "in mempool"
        print(f"  {'+' if delta >= 0 else '-'}{btc(abs(delta))} BTC  {tx['txid']}  ({where})")


def main():
    parser = argparse.ArgumentParser(description="Bitcoin address balance")
    parser.add_argument("address")
    parser.add_argument("--txs", type=int, nargs="?", const=10, metavar="N")
    parser.add_argument("--utxo", action="store_true")
    args = parser.parse_args()

    balance = api.get_balance(args.address)
    print(f"Address:      {args.address}")
    print(f"Balance:      {btc(balance['total'])} BTC ({balance['total']} sat)")
    if balance["pending"]:
        print(f"  of which in mempool: {btc(balance['pending'])} BTC")
    print(f"Transactions: {balance['tx_count']}")

    if args.txs:
        print("\nRecent transactions:")
        show_transactions(args.address, args.txs)

    if args.utxo:
        print("\nUnspent outputs:")
        utxos = api.get_utxos(args.address, confirmed_only=False)
        for utxo in utxos:
            state = "confirmed" if utxo["status"]["confirmed"] else "in mempool"
            print(f"  {utxo['value']:>8} sat  {utxo['txid']}:{utxo['vout']}  ({state})")
        if not utxos:
            print("  none")


if __name__ == "__main__":
    main()
