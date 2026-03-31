import os
from typing import Dict, Optional

import boto3

from crypto import (
    SECP256K1_N,
    keccak256,
    normalize_signature_s,
    parse_der_signature,
    parse_kms_public_key,
    pubkey_to_address,
    recover_address,
    signature_to_hex,
)


class KmsSigner:
    def __init__(self, key_id: str) -> None:
        self._key_id = key_id
        self._kms = boto3.client("kms")
        self._cached_pubkey = None
        self._cached_address = None

    def _load_pubkey(self) -> str:
        if self._cached_address:
            return self._cached_address
        response = self._kms.get_public_key(KeyId=self._key_id)
        pubkey = parse_kms_public_key(response["PublicKey"])
        address = pubkey_to_address(pubkey)
        self._cached_pubkey = pubkey
        self._cached_address = address
        return address

    def sign_digest(self, digest: bytes) -> Dict[str, str]:
        if len(digest) != 32:
            raise ValueError("digest must be 32 bytes")
        response = self._kms.sign(
            KeyId=self._key_id,
            Message=digest,
            MessageType="DIGEST",
            SigningAlgorithm="ECDSA_SHA_256",
        )
        r, s = parse_der_signature(response["Signature"])
        if not (1 <= r < SECP256K1_N and 1 <= s < SECP256K1_N):
            raise ValueError("signature out of range")
        r, s, _ = normalize_signature_s(r, s)

        signer = self._load_pubkey()
        v = None
        for rec_id in (0, 1):
            recovered = recover_address(digest, r, s, rec_id)
            if recovered.lower() == signer.lower():
                v = rec_id + 27
                break
        if v is None:
            raise ValueError("unable to recover v for signature")

        return {
            "signature": signature_to_hex(r, s, v),
            "signer": signer,
            "r": hex(r),
            "s": hex(s),
            "v": v,
        }
