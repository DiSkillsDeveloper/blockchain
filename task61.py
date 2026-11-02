import argparse
import hashlib
import os
import time

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, P2shAddress
from bip_utils import Bip39SeedGenerator, Bip32Slip10Secp256k1

import api

setup("testnet")

BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def to_wif(key_bytes):
    payload = b"\xef" + key_bytes + b"\x01"
    payload += hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]

    number, out = int.from_bytes(payload, "big"), ""
    while number:
        number, rest = divmod(number, 58)
        out = BASE58[rest] + out
    return out


def addresses_at(root, path):
    node = root.DerivePath(path)
    key = PrivateKey.from_wif(to_wif(node.PrivateKey().Raw().ToBytes()))
    pub = key.get_public_key()
    segwit = pub.get_segwit_address()

    return key, {
        "SegWit": segwit.to_string(),
        "Legacy": pub.get_address().to_string(),
        "SegWit in P2SH": P2shAddress.from_script(segwit.to_script_pub_key()).to_string(),
    }


def branches(args):
    for purpose in args.purposes:
        for coin in args.coins:
            for account in args.accounts:
                for chain in (0, 1):
                    yield f"m/{purpose}'/{coin}'/{account}'/{chain}"


def save(key, out, path, address, kind):
    with open(out, "w") as f:
        f.write(key.to_wif() + "\n")
    os.chmod(out, 0o600)
    print(f"\nKey saved to {out}")
    print(f"Path: {path}, type {kind}")
    print(f"Address: {address}")


def match(root, target, args):
    print(f"Searching for the path to address {target}\n")
    for branch in branches(args):
        for i in range(args.gap):
            key, found = addresses_at(root, f"{branch}/{i}")
            for kind, address in found.items():
                if address == target:
                    print(f"Found: {branch}/{i}")
                    save(key, args.out, f"{branch}/{i}", address, kind)
                    return
    print("Not found, try --accounts 0 1 2 3 --gap 40")


def scan_chain(root, chain, gap):
    found, empty, i = [], 0, 0
    while empty < gap:
        key, addresses = addresses_at(root, f"{chain}/{i}")
        used = False

        for kind, address in addresses.items():
            balance = api.get_balance(address)
            time.sleep(0.2)
            if not balance["tx_count"]:
                continue

            used = True
            print(f"  {chain}/{i} {kind}: {address} - {balance['total']} sat")
            found.append((key, f"{chain}/{i}", address, balance["total"], kind))

        empty = 0 if used else empty + 1
        i += 1
    return found


def scan(root, args):
    print("Scanning addresses and checking balances.\n")
    found = []

    for purpose in args.purposes:
        for coin in args.coins:
            account = 0
            while True:
                base = f"m/{purpose}'/{coin}'/{account}'"
                external = scan_chain(root, f"{base}/0", args.gap)
                if not external:
                    break
                found += external + scan_chain(root, f"{base}/1", args.gap)
                account += 1

    with_coins = [f for f in found if f[3]]
    if not with_coins:
        raise SystemExit("\nNo addresses with coins found.")

    key, path, address, total, kind = max(with_coins, key=lambda f: f[3])
    print(f"\nBest address: {address} ({total} sat)")
    save(key, args.out, path, address, kind)


def main():
    parser = argparse.ArgumentParser(description="Import a key and scan addresses")
    parser.add_argument("--seed", default="seed.txt")
    parser.add_argument("--match", metavar="ADDRESS")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--out", default="found.wif")
    parser.add_argument("--gap", type=int, default=20)
    parser.add_argument("--purposes", type=int, nargs="+", default=[44, 49, 84])
    parser.add_argument("--coins", type=int, nargs="+", default=[1])
    parser.add_argument("--accounts", type=int, nargs="+", default=[0, 1])
    args = parser.parse_args()

    with open(args.seed) as f:
        phrase = f.read().strip()
    print(f"Seed phrase of {len(phrase.split())} words")

    root = Bip32Slip10Secp256k1.FromSeed(Bip39SeedGenerator(phrase).Generate())

    if args.match:
        match(root, args.match, args)
    elif args.scan:
        scan(root, args)
    else:
        raise SystemExit("--match <address> or --scan")


if __name__ == "__main__":
    main()
