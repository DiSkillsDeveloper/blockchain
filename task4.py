import argparse
import os

from bitcoinutils.setup import setup
from bitcoinutils.keys import PrivateKey, P2shAddress

import api

setup("testnet")


def main():
    parser = argparse.ArgumentParser(description="Bitcoin key and addresses")
    parser.add_argument("file", nargs="?", default="key.wif")
    parser.add_argument("--new", action="store_true")
    args = parser.parse_args()

    if args.new:
        if os.path.exists(args.file):
            raise SystemExit(f"{args.file} already exists")
        with open(args.file, "w") as f:
            f.write(PrivateKey().to_wif() + "\n")
        os.chmod(args.file, 0o600)
        print(f"Key created: {args.file}")

    with open(args.file) as f:
        key = PrivateKey.from_wif(f.read().strip())

    pub = key.get_public_key()
    legacy = pub.get_address()
    segwit = pub.get_segwit_address()
    nested = P2shAddress.from_script(segwit.to_script_pub_key())

    print(f"Public key: {pub.to_hex()}")
    print(f"HASH160:    {legacy.to_hash160()}\n")
    print(f"Legacy (P2PKH):    {legacy.to_string()}")
    print(f"SegWit (P2WPKH):   {segwit.to_string()}")
    print(f"SegWit in P2SH:    {nested.to_string()}")

    print("\nBalances:")
    for name, address in (("Legacy", legacy), ("SegWit", segwit)):
        balance = api.get_balance(address.to_string())
        print(f"  {name:7} {balance['total']:>8} sat, transactions: {balance['tx_count']}")


if __name__ == "__main__":
    main()
