#!/usr/bin/env python3
import argparse
import os
import sys

import boto3

from aws.crypto import parse_kms_public_key, pubkey_to_address


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive Ethereum address from a KMS secp256k1 key")
    parser.add_argument("--key-id", help="KMS key ID or ARN (or set KMS_KEY_ID)")
    parser.add_argument("--region", help="AWS region override")
    args = parser.parse_args()

    key_id = args.key_id or os.environ.get("KMS_KEY_ID")
    if not key_id:
        print("KMS key id is required (use --key-id or KMS_KEY_ID)", file=sys.stderr)
        return 2

    client = boto3.client("kms", region_name=args.region) if args.region else boto3.client("kms")
    response = client.get_public_key(KeyId=key_id)
    pubkey = parse_kms_public_key(response["PublicKey"])
    print(pubkey_to_address(pubkey))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
