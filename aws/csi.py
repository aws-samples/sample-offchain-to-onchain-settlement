from dataclasses import dataclass
from typing import Dict, Tuple

from crypto import keccak256

INTENT_MAP = {
    "MINT_ONLY": 0,
    "BURN_AND_MINT": 1,
    "BURN_ONLY": 2,
}

INTENT_NAMES = {v: k for k, v in INTENT_MAP.items()}

DOMAIN_NAME = "SettlementInstruction"
DOMAIN_VERSION = "1"

DOMAIN_TYPE = "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
CSI_TYPE = (
    "CanonicalSettlementInstruction(bytes32 instructionId,bytes32 messageDigest,address asset,"
    "uint256 amount,address fromParty,address toParty,uint64 valueTime,uint64 createdAt,uint64 expiry,"
    "uint8 intent,uint256 chainId,bytes32 nonce)"
)


@dataclass(frozen=True)
class CanonicalSettlementInstruction:
    instruction_id: bytes
    message_digest: bytes
    asset: str
    amount: int
    from_party: str
    to_party: str
    value_time: int
    created_at: int
    expiry: int
    intent: int
    chain_id: int
    nonce: bytes

    def to_dict(self) -> Dict[str, str]:
        return {
            "instructionId": "0x" + self.instruction_id.hex(),
            "messageDigest": "0x" + self.message_digest.hex(),
            "asset": self.asset,
            "amount": str(self.amount),
            "fromParty": self.from_party,
            "toParty": self.to_party,
            "valueTime": self.value_time,
            "createdAt": self.created_at,
            "expiry": self.expiry,
            "intent": INTENT_NAMES.get(self.intent, "UNKNOWN"),
            "chainId": self.chain_id,
            "nonce": "0x" + self.nonce.hex(),
        }


def _strip_0x(value: str) -> str:
    return value[2:] if value.startswith("0x") else value


def _encode_bytes32(value: bytes) -> bytes:
    if len(value) != 32:
        raise ValueError("bytes32 must be 32 bytes")
    return value


def _encode_uint256(value: int) -> bytes:
    if value < 0:
        raise ValueError("uint256 cannot be negative")
    return value.to_bytes(32, "big")


def _encode_uint64(value: int) -> bytes:
    if value < 0 or value >= 1 << 64:
        raise ValueError("uint64 out of range")
    return value.to_bytes(32, "big")


def _encode_uint8(value: int) -> bytes:
    if value < 0 or value >= 1 << 8:
        raise ValueError("uint8 out of range")
    return value.to_bytes(32, "big")


def _encode_address(address: str) -> bytes:
    addr = bytes.fromhex(_strip_0x(address))
    if len(addr) != 20:
        raise ValueError("address must be 20 bytes")
    return b"\x00" * 12 + addr


def _hash_text(value: str) -> bytes:
    return keccak256(value.encode("utf-8"))


def eip712_domain_separator(chain_id: int, verifying_contract: str) -> bytes:
    type_hash = keccak256(DOMAIN_TYPE.encode("utf-8"))
    return keccak256(
        type_hash
        + _hash_text(DOMAIN_NAME)
        + _hash_text(DOMAIN_VERSION)
        + _encode_uint256(chain_id)
        + _encode_address(verifying_contract)
    )


def hash_csi(csi: CanonicalSettlementInstruction) -> bytes:
    type_hash = keccak256(CSI_TYPE.encode("utf-8"))
    return keccak256(
        type_hash
        + _encode_bytes32(csi.instruction_id)
        + _encode_bytes32(csi.message_digest)
        + _encode_address(csi.asset)
        + _encode_uint256(csi.amount)
        + _encode_address(csi.from_party)
        + _encode_address(csi.to_party)
        + _encode_uint64(csi.value_time)
        + _encode_uint64(csi.created_at)
        + _encode_uint64(csi.expiry)
        + _encode_uint8(csi.intent)
        + _encode_uint256(csi.chain_id)
        + _encode_bytes32(csi.nonce)
    )


def hash_typed_data(csi: CanonicalSettlementInstruction, chain_id: int, verifying_contract: str) -> bytes:
    domain_separator = eip712_domain_separator(chain_id, verifying_contract)
    struct_hash = hash_csi(csi)
    return keccak256(b"\x19\x01" + domain_separator + struct_hash)


def derive_instruction_id(
    message_digest: bytes,
    asset: str,
    amount: int,
    from_party: str,
    to_party: str,
    value_time: int,
    intent: int,
    chain_id: int,
    created_at: int,
    expiry: int,
    nonce: bytes,
) -> bytes:
    packed = (
        b"CSI_V1"
        + message_digest
        + bytes.fromhex(_strip_0x(asset))
        + amount.to_bytes(32, "big")
        + bytes.fromhex(_strip_0x(from_party))
        + bytes.fromhex(_strip_0x(to_party))
        + value_time.to_bytes(8, "big")
        + intent.to_bytes(1, "big")
        + chain_id.to_bytes(32, "big")
        + created_at.to_bytes(8, "big")
        + expiry.to_bytes(8, "big")
        + nonce
    )
    return keccak256(packed)


def idempotency_key(
    message_digest: bytes,
    asset: str,
    amount: int,
    from_party: str,
    to_party: str,
    value_time: int,
    intent: int,
    chain_id: int,
    reference: str,
) -> bytes:
    ref_hash = keccak256(reference.encode("utf-8")) if reference else b"\x00" * 32
    packed = (
        b"CSI_IDEMPOTENCY_V1"
        + message_digest
        + bytes.fromhex(_strip_0x(asset))
        + amount.to_bytes(32, "big")
        + bytes.fromhex(_strip_0x(from_party))
        + bytes.fromhex(_strip_0x(to_party))
        + value_time.to_bytes(8, "big")
        + intent.to_bytes(1, "big")
        + chain_id.to_bytes(32, "big")
        + ref_hash
    )
    return keccak256(packed)


def typed_data_payload(csi: CanonicalSettlementInstruction, verifying_contract: str) -> Dict:
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "CanonicalSettlementInstruction": [
                {"name": "instructionId", "type": "bytes32"},
                {"name": "messageDigest", "type": "bytes32"},
                {"name": "asset", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "fromParty", "type": "address"},
                {"name": "toParty", "type": "address"},
                {"name": "valueTime", "type": "uint64"},
                {"name": "createdAt", "type": "uint64"},
                {"name": "expiry", "type": "uint64"},
                {"name": "intent", "type": "uint8"},
                {"name": "chainId", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "CanonicalSettlementInstruction",
        "domain": {
            "name": DOMAIN_NAME,
            "version": DOMAIN_VERSION,
            "chainId": csi.chain_id,
            "verifyingContract": verifying_contract,
        },
        "message": {
            "instructionId": "0x" + csi.instruction_id.hex(),
            "messageDigest": "0x" + csi.message_digest.hex(),
            "asset": csi.asset,
            "amount": str(csi.amount),
            "fromParty": csi.from_party,
            "toParty": csi.to_party,
            "valueTime": csi.value_time,
            "createdAt": csi.created_at,
            "expiry": csi.expiry,
            "intent": csi.intent,
            "chainId": csi.chain_id,
            "nonce": "0x" + csi.nonce.hex(),
        },
    }


def validate_intent(intent: str) -> int:
    if intent not in INTENT_MAP:
        raise ValueError("intent must be MINT_ONLY, BURN_AND_MINT, or BURN_ONLY")
    return INTENT_MAP[intent]


def build_csi(
    instruction_id: bytes,
    message_digest: bytes,
    asset: str,
    amount: int,
    from_party: str,
    to_party: str,
    value_time: int,
    created_at: int,
    expiry: int,
    intent: int,
    chain_id: int,
    nonce: bytes,
) -> CanonicalSettlementInstruction:
    return CanonicalSettlementInstruction(
        instruction_id=instruction_id,
        message_digest=message_digest,
        asset=asset,
        amount=amount,
        from_party=from_party,
        to_party=to_party,
        value_time=value_time,
        created_at=created_at,
        expiry=expiry,
        intent=intent,
        chain_id=chain_id,
        nonce=nonce,
    )


__all__ = [
    "CanonicalSettlementInstruction",
    "DOMAIN_NAME",
    "DOMAIN_VERSION",
    "DOMAIN_TYPE",
    "CSI_TYPE",
    "derive_instruction_id",
    "idempotency_key",
    "build_csi",
    "validate_intent",
    "hash_typed_data",
    "hash_csi",
    "eip712_domain_separator",
    "typed_data_payload",
]
