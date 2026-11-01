import argparse

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, P2pkhAddress, P2wpkhAddress
from bitcoinutils.script import Script
from bitcoinutils.transactions import Transaction, TxInput, TxOutput

import api

setup("testnet")

DUST = 546


def to_script(address):
    if address.startswith("tb1"):
        return P2wpkhAddress.from_address(address).to_script_pub_key()
    return P2pkhAddress.from_address(address).to_script_pub_key()


def size(inputs, outputs):
    return 10 + 148 * inputs + 34 * outputs


def main():
    parser = argparse.ArgumentParser(description="Spend from a Legacy address")
    parser.add_argument("to_address")
    parser.add_argument("amount", type=int)
    parser.add_argument("--key", default="key.wif")
    parser.add_argument("--fee-rate", type=int)
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()

    with open(args.key) as f:
        key = PrivateKey.from_wif(f.read().strip())
    pub = key.get_public_key()
    sender = pub.get_address()

    print(f"Sender:    {sender.to_string()}")
    print(f"Recipient: {args.to_address}")
    print(f"Amount:    {args.amount} sat\n")

    fee_rate = args.fee_rate or api.get_fee_rate()
    chosen, total = [], 0
    for utxo in api.get_utxos(sender.to_string()):
        chosen.append(utxo)
        total += utxo["value"]
        fee = size(len(chosen), 2) * fee_rate
        if total >= args.amount + fee:
            break
    else:
        raise SystemExit(f"Insufficient funds: have {total} sat")

    change = total - args.amount - fee
    if change < DUST:
        fee, change = fee + change, 0

    print(f"Inputs: {len(chosen)} totaling {total} sat")
    print(f"Fee:    {fee} sat at {fee_rate} sat/vB")
    print(f"Change: {change} sat\n")

    inputs = [TxInput(u["txid"], u["vout"]) for u in chosen]
    outputs = [TxOutput(args.amount, to_script(args.to_address))]
    if change:
        outputs.append(TxOutput(change, sender.to_script_pub_key()))

    tx = Transaction(inputs, outputs)

    for i, txin in enumerate(inputs):
        signature = key.sign_input(tx, i, sender.to_script_pub_key())
        txin.script_sig = Script([signature, pub.to_hex()])

    raw = tx.serialize()
    print(f"TXID: {tx.get_txid()}")
    print(f"Size: {len(raw) // 2} bytes\n{raw}\n")

    assert total == args.amount + change + fee

    if not args.send:
        print("Dry run")
        return

    txid = api.broadcast(raw)
    print(f"Sent: {txid}\n{api.link(txid)}")


if __name__ == "__main__":
    main()
