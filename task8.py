import argparse
import os

import requests

URL = "http://127.0.0.1:48332"
COOKIE = os.path.expanduser("~/.bitcoin/testnet4/.cookie")


def rpc(method, params, args, wallet=False):
    if args.user:
        auth = (args.user, args.password or "")
    else:
        with open(args.cookie) as f:
            auth = tuple(f.read().strip().split(":", 1))

    url = args.url + (f"/wallet/{args.wallet}" if wallet else "")
    body = requests.post(url, json={"method": method, "params": params, "id": "lab"},
                         auth=auth, timeout=60).json()

    if body.get("error"):
        raise SystemExit(f"Node returned an error: {body['error']['message']}")
    return body["result"]


def main():
    parser = argparse.ArgumentParser(description="Bitcoin Core over JSON-RPC")
    parser.add_argument("command",
                        choices=["info", "balance", "newaddress", "send", "broadcast"])
    parser.add_argument("target", nargs="?")
    parser.add_argument("amount", nargs="?", type=int)
    parser.add_argument("--url", default=URL)
    parser.add_argument("--wallet", default="lab")
    parser.add_argument("--cookie", default=COOKIE)
    parser.add_argument("--user")
    parser.add_argument("--password")
    args = parser.parse_args()

    if args.command == "info":
        chain = rpc("getblockchaininfo", [], args)
        progress = chain["verificationprogress"] * 100
        print(f"Network: {chain['chain']}")
        print(f"Blocks:  {chain['blocks']} of {chain['headers']}")
        print(f"Synced:  {progress:.2f}%")
        print(f"Pruning: {'enabled' if chain.get('pruned') else 'disabled'}")
        if progress < 99.9:
            print("\nThe node is still syncing, the balance will be incomplete.")

    elif args.command == "balance":
        balance = rpc("getbalance", [], args, wallet=True)
        print(f"Balance: {balance} BTC ({int(balance * 1e8)} sat)")
        for entry in rpc("listreceivedbyaddress", [0, True], args, wallet=True):
            print(f"  {entry['address']}  {entry['amount']} BTC")

    elif args.command == "newaddress":
        print("New address:", rpc("getnewaddress", ["", "bech32"], args, wallet=True))

    elif args.command == "send":
        txid = rpc("sendtoaddress", [args.target, args.amount / 1e8], args, wallet=True)
        print(f"Sent {args.amount} sat to {args.target}")
        print(f"TXID: {txid}\nhttps://mempool.space/testnet4/tx/{txid}")

    else:
        txid = rpc("sendrawtransaction", [args.target], args)
        print(f"Node accepted the transaction.")
        print(f"TXID: {txid}\nhttps://mempool.space/testnet4/tx/{txid}")


if __name__ == "__main__":
    main()
