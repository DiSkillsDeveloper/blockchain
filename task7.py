import argparse
import json
import os

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, P2shAddress, P2pkhAddress, P2wpkhAddress
from bitcoinutils.script import Script
from bitcoinutils.transactions import Transaction, TxInput, TxOutput

import api

setup("testnet")

WALLET = "multisig.json"
DUST = 546


def redeem_script(pubkeys):
    return Script(["OP_2"] + [k.to_hex() for k in pubkeys] + ["OP_2", "OP_CHECKMULTISIG"])


def to_script(address):
    if address.startswith("tb1"):
        return P2wpkhAddress.from_address(address).to_script_pub_key()
    if address.startswith("2"):
        return P2shAddress.from_address(address).to_script_pub_key()
    return P2pkhAddress.from_address(address).to_script_pub_key()


def create():
    if os.path.exists(WALLET):
        raise SystemExit(f"{WALLET} already exists")

    keys = [PrivateKey(), PrivateKey()]
    script = redeem_script([k.get_public_key() for k in keys])
    address = P2shAddress.from_script(script)

    with open(WALLET, "w") as f:
        json.dump({"address": address.to_string(),
                   "keys": [k.to_wif() for k in keys],
                   "redeem_script": script.to_hex()}, f, indent=2)
    os.chmod(WALLET, 0o600)

    print(f"2-of-2 wallet created: {WALLET}\n")
    print(f"Address: {address.to_string()}")
    print(f"Script:  {script.to_hex()}")


def load():
    with open(WALLET) as f:
        data = json.load(f)
    keys = [PrivateKey.from_wif(w) for w in data["keys"]]
    return data["address"], keys, redeem_script([k.get_public_key() for k in keys])


def show():
    address, _, script = load()
    balance = api.get_balance(address)

    print(f"Address: {address}")
    print(f"Script:  {script.to_hex()}")
    print(f"Balance: {balance['total']} sat, {balance['tx_count']} transactions")

    for utxo in api.get_utxos(address, confirmed_only=False):
        state = "confirmed" if utxo["status"]["confirmed"] else "in mempool"
        print(f"  {utxo['value']:>8} sat  {utxo['txid']}:{utxo['vout']}  ({state})")


def send(to_address, amount, fee_rate, really_send):
    address, keys, script = load()

    print(f"Sender:    {address} (2 of 2)")
    print(f"Recipient: {to_address}")
    print(f"Amount:    {amount} sat\n")

    fee_rate = fee_rate or api.get_fee_rate()
    chosen, total = [], 0
    for utxo in api.get_utxos(address):
        chosen.append(utxo)
        total += utxo["value"]
        fee = (10 + 300 * len(chosen) + 34 * 2) * fee_rate
        if total >= amount + fee:
            break
    else:
        raise SystemExit(f"Insufficient funds: have {total} sat")

    change = total - amount - fee
    if change < DUST:
        fee, change = fee + change, 0

    print(f"Inputs: {len(chosen)} totaling {total} sat")
    print(f"Fee:    {fee} sat at {fee_rate} sat/vB")
    print(f"Change: {change} sat\n")

    inputs = [TxInput(u["txid"], u["vout"]) for u in chosen]
    outputs = [TxOutput(amount, to_script(to_address))]
    if change:
        outputs.append(TxOutput(change, to_script(address)))

    tx = Transaction(inputs, outputs)

    for i, txin in enumerate(inputs):
        signatures = [k.sign_input(tx, i, script) for k in keys]
        txin.script_sig = Script(["OP_0"] + signatures + [script.to_hex()])

    raw = tx.serialize()
    print(f"TXID: {tx.get_txid()}")
    print(f"Size: {len(raw) // 2} bytes\n{raw}\n")

    assert total == amount + change + fee

    if not really_send:
        print("Dry run. Use --send to broadcast.")
        return

    txid = api.broadcast(raw)
    print(f"Sent: {txid}\n{api.link(txid)}")


def main():
    parser = argparse.ArgumentParser(description="2-of-2 multisig")
    parser.add_argument("command", choices=["create", "show", "send"])
    parser.add_argument("to_address", nargs="?")
    parser.add_argument("amount", nargs="?", type=int)
    parser.add_argument("--fee-rate", type=int)
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()

    if args.command == "create":
        create()
    elif args.command == "show":
        show()
    else:
        if not args.to_address or args.amount is None:
            raise SystemExit("Recipient address and amount are required")
        send(args.to_address, args.amount, args.fee_rate, args.send)


if __name__ == "__main__":
    main()
