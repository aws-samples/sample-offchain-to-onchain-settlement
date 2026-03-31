import hashlib
import hmac
from typing import Tuple

# Keccak-256 implementation (SHA-3 variant used by Ethereum)
_KECCAK_ROUNDS = 24
_KECCAK_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808a, 0x8000000080008000,
    0x000000000000808b, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008a, 0x0000000000000088, 0x0000000080008009, 0x000000008000000a,
    0x000000008000808b, 0x800000000000008b, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800a, 0x800000008000000a,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_KECCAK_ROT = [
    [0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56], [27, 20, 39, 8, 14],
]


def _keccak_f(state):
    for rc in _KECCAK_RC:
        # θ step
        c = [state[x][0] ^ state[x][1] ^ state[x][2] ^ state[x][3] ^ state[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ (((c[(x + 1) % 5] << 1) | (c[(x + 1) % 5] >> 63)) & ((1 << 64) - 1)) for x in range(5)]
        for x in range(5):
            for y in range(5):
                state[x][y] ^= d[x]
        # ρ and π steps
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                rot = _KECCAK_ROT[x][y]
                b[y][(2 * x + 3 * y) % 5] = ((state[x][y] << rot) | (state[x][y] >> (64 - rot))) & ((1 << 64) - 1)
        # χ step
        for x in range(5):
            for y in range(5):
                state[x][y] = b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y])
        # ι step
        state[0][0] ^= rc


def keccak256(data: bytes) -> bytes:
    rate = 136  # (1600 - 256*2) // 8
    state = [[0] * 5 for _ in range(5)]
    # Absorb
    data = bytearray(data)
    data.append(0x01)
    while len(data) % rate != 0:
        data.append(0)
    data[-1] |= 0x80
    for i in range(0, len(data), rate):
        block = data[i:i + rate]
        for j in range(rate // 8):
            x, y = j % 5, j // 5
            state[x][y] ^= int.from_bytes(block[j * 8:(j + 1) * 8], 'little')
        _keccak_f(state)
    # Squeeze
    out = b''
    for y in range(5):
        for x in range(5):
            out += state[x][y].to_bytes(8, 'little')
            if len(out) >= 32:
                return out[:32]
    return out[:32]


SECP256K1_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
SECP256K1_GX = 55066263022277343669578718895168534326250603453777594175500187360389116729240
SECP256K1_GY = 32670510020758816978083085130507043184471273380659243275938904335757337482424


class Point:
    __slots__ = ("x", "y")

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def is_infinity(self) -> bool:
        return self.x is None or self.y is None


INFINITY = Point(None, None)


def _inv_mod(value: int, modulus: int) -> int:
    return pow(value, -1, modulus)


def _point_add(p: Point, q: Point) -> Point:
    if p.is_infinity():
        return q
    if q.is_infinity():
        return p
    if p.x == q.x and (p.y != q.y or p.y == 0):
        return INFINITY

    if p.x == q.x and p.y == q.y:
        lam = (3 * p.x * p.x) * _inv_mod(2 * p.y, SECP256K1_P)
    else:
        lam = (q.y - p.y) * _inv_mod((q.x - p.x) % SECP256K1_P, SECP256K1_P)

    lam %= SECP256K1_P
    x_r = (lam * lam - p.x - q.x) % SECP256K1_P
    y_r = (lam * (p.x - x_r) - p.y) % SECP256K1_P
    return Point(x_r, y_r)


def _point_mul(k: int, point: Point) -> Point:
    if k % SECP256K1_N == 0 or point.is_infinity():
        return INFINITY
    result = INFINITY
    addend = point
    while k:
        if k & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return result


def _rfc6979_generate_k(msg_hash: bytes, priv_key: int) -> int:
    if len(msg_hash) != 32:
        raise ValueError("msg_hash must be 32 bytes")
    x = priv_key.to_bytes(32, "big")
    h1 = msg_hash
    v = b"\x01" * 32
    k = b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + x + h1, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + x + h1, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        v = hmac.new(k, v, hashlib.sha256).digest()
        candidate = int.from_bytes(v, "big")
        if 1 <= candidate < SECP256K1_N:
            return candidate
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def secp256k1_sign(msg_hash: bytes, priv_key: int) -> Tuple[int, int, int]:
    if not (1 <= priv_key < SECP256K1_N):
        raise ValueError("invalid private key")
    k = _rfc6979_generate_k(msg_hash, priv_key)
    r_point = _point_mul(k, Point(SECP256K1_GX, SECP256K1_GY))
    if r_point.is_infinity():
        raise ValueError("invalid R point")
    r = r_point.x % SECP256K1_N
    if r == 0:
        raise ValueError("invalid r value")
    k_inv = _inv_mod(k, SECP256K1_N)
    z = int.from_bytes(msg_hash, "big")
    s = (k_inv * (z + r * priv_key)) % SECP256K1_N
    if s == 0:
        raise ValueError("invalid s value")

    rec_id = 0 if (r_point.y % 2 == 0) else 1
    if s > SECP256K1_N // 2:
        s = SECP256K1_N - s
        rec_id ^= 1
    v = rec_id + 27
    return r, s, v


def secp256k1_pubkey(priv_key: int) -> Point:
    if not (1 <= priv_key < SECP256K1_N):
        raise ValueError("invalid private key")
    return _point_mul(priv_key, Point(SECP256K1_GX, SECP256K1_GY))


def pubkey_to_address(pubkey: Point) -> str:
    if pubkey.is_infinity():
        raise ValueError("invalid public key")
    x_bytes = pubkey.x.to_bytes(32, "big")
    y_bytes = pubkey.y.to_bytes(32, "big")
    addr = keccak256(x_bytes + y_bytes)[-20:]
    return "0x" + addr.hex()


def signature_to_bytes(r: int, s: int, v: int) -> bytes:
    return r.to_bytes(32, "big") + s.to_bytes(32, "big") + bytes([v])


def signature_to_hex(r: int, s: int, v: int) -> str:
    return "0x" + signature_to_bytes(r, s, v).hex()


def _read_asn1_length(data: bytes, offset: int) -> Tuple[int, int]:
    if offset >= len(data):
        raise ValueError("ASN.1 length out of bounds")
    first = data[offset]
    if first < 0x80:
        return first, offset + 1
    length_of_length = first & 0x7F
    if length_of_length == 0 or offset + 1 + length_of_length > len(data):
        raise ValueError("ASN.1 length invalid")
    length = int.from_bytes(data[offset + 1:offset + 1 + length_of_length], "big")
    return length, offset + 1 + length_of_length


def parse_der_signature(der_sig: bytes) -> Tuple[int, int]:
    if not der_sig or der_sig[0] != 0x30:
        raise ValueError("DER signature must start with SEQUENCE")
    seq_len, offset = _read_asn1_length(der_sig, 1)
    end = offset + seq_len
    if end > len(der_sig):
        raise ValueError("DER signature truncated")
    if der_sig[offset] != 0x02:
        raise ValueError("DER signature missing INTEGER for r")
    r_len, offset = _read_asn1_length(der_sig, offset + 1)
    r_bytes = der_sig[offset:offset + r_len]
    offset += r_len
    if der_sig[offset] != 0x02:
        raise ValueError("DER signature missing INTEGER for s")
    s_len, offset = _read_asn1_length(der_sig, offset + 1)
    s_bytes = der_sig[offset:offset + s_len]
    r = int.from_bytes(r_bytes, "big")
    s = int.from_bytes(s_bytes, "big")
    return r, s


def parse_kms_public_key(der_pubkey: bytes) -> Point:
    if not der_pubkey or der_pubkey[0] != 0x30:
        raise ValueError("Invalid public key")
    _, offset = _read_asn1_length(der_pubkey, 1)
    if der_pubkey[offset] != 0x30:
        raise ValueError("Invalid public key algorithm sequence")
    alg_len, offset = _read_asn1_length(der_pubkey, offset + 1)
    offset += alg_len
    if der_pubkey[offset] != 0x03:
        raise ValueError("Invalid public key bit string")
    bit_len, offset = _read_asn1_length(der_pubkey, offset + 1)
    if offset >= len(der_pubkey) or der_pubkey[offset] != 0x00:
        raise ValueError("Invalid public key bit padding")
    offset += 1
    pubkey_bytes = der_pubkey[offset:offset + bit_len - 1]
    if len(pubkey_bytes) != 65 or pubkey_bytes[0] != 0x04:
        raise ValueError("Expected uncompressed public key")
    x = int.from_bytes(pubkey_bytes[1:33], "big")
    y = int.from_bytes(pubkey_bytes[33:], "big")
    point = Point(x, y)
    if not _is_on_curve(point):
        raise ValueError("Public key not on curve")
    return point


def _is_on_curve(point: Point) -> bool:
    if point.is_infinity():
        return False
    return (point.y * point.y - (point.x * point.x * point.x + 7)) % SECP256K1_P == 0


def _negate_point(point: Point) -> Point:
    if point.is_infinity():
        return point
    return Point(point.x, (-point.y) % SECP256K1_P)


def recover_public_key(msg_hash: bytes, r: int, s: int, rec_id: int) -> Point:
    if rec_id not in (0, 1):
        raise ValueError("rec_id must be 0 or 1")
    if len(msg_hash) != 32:
        raise ValueError("msg_hash must be 32 bytes")
    x = r
    if x >= SECP256K1_P:
        raise ValueError("r out of range")
    alpha = (x * x * x + 7) % SECP256K1_P
    beta = pow(alpha, (SECP256K1_P + 1) // 4, SECP256K1_P)
    y = beta if (beta % 2 == rec_id) else (SECP256K1_P - beta)
    r_point = Point(x, y)
    if not _is_on_curve(r_point):
        raise ValueError("R point not on curve")
    r_inv = _inv_mod(r, SECP256K1_N)
    z = int.from_bytes(msg_hash, "big") % SECP256K1_N
    s_r = _point_mul(s % SECP256K1_N, r_point)
    z_g = _point_mul(z, Point(SECP256K1_GX, SECP256K1_GY))
    q = _point_add(s_r, _negate_point(z_g))
    q = _point_mul(r_inv, q)
    return q


def recover_address(msg_hash: bytes, r: int, s: int, rec_id: int) -> str:
    pub = recover_public_key(msg_hash, r, s, rec_id)
    return pubkey_to_address(pub)


def normalize_signature_s(r: int, s: int) -> Tuple[int, int, int]:
    rec_id = 0
    if s > SECP256K1_N // 2:
        s = SECP256K1_N - s
        rec_id ^= 1
    return r, s, rec_id
