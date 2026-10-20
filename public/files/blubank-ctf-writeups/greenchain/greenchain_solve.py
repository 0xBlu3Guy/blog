#!/usr/bin/env python3
"""
GreenChain — full off-device flag recovery PoC.

Challenge : GreenChain (Android APK, package com.invoxes.greenchain)
Target    : /home/kali/BlueCTF/GreenChain/evidence/extracted/GreenChain.apk
Artifacts : /home/kali/BlueCTF/GreenChain/tools/assets/{season.txt,steward.dat,flag.dat}

This script re-implements, in Python, exactly the chain performed by
com.invoxes.greenchain.crypto.StewardVault / StewardClaim / Secp256k1:

  1. salt        = "eco-" + season.txt.trim()                 ("eco-2026")
  2. AES-128 key = SHA256( packageName + salt )[0:16]
                 = SHA256("com.invoxes.greenchaineco-2026")[0:16]
  3. steward.dat = IV(16) || AES-CBC(PKCS5)-ciphertext(80)
                 -> decrypt to the steward secp256k1 PRIVATE key (hex)
  4. ECDSA (secp256k1, deterministic k) sign SHA256("greenchain-claim:v1")
     with that private key; encode r,s as DER SEQUENCE { INTEGER r, INTEGER s },
     hex-encode -> the "steward signature" the app's ClaimActivity expects.
  5. The signature is verified in-app against the hard-coded
     STEWARD_PUBKEY_HEX (also verified here, independently).
  6. flag.dat   = IV(16) || AES-CBC(PKCS5)-ciphertext(48)
     flag AES-128 key = SHA256( privkey_hex + "flag" )[0:16]
     -> decrypt to the flag.

Dependencies: python3 stdlib + `cryptography` (AES-CBC). secp256k1 is implemented
inline so there is no elliptic-curve library dependency.

Usage:
  python3 greenchain_solve.py                # uses default paths
  python3 greenchain_solve.py <apk_or_assets_dir>
"""

import hashlib
import os
import struct
import sys
from binascii import hexlify, unhexlify

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# ---------------------------------------------------------------- constants ---
# Straight out of StewardVault.java (classes4.dex)
CLAIM_MESSAGE = "greenchain-claim:v1"
SALT_PREFIX = "eco-"
STEWARD_PUBKEY_HEX = (
    "041c44e3f125897027892cd90ae3b4246ad4c65a99bccdf3cd3f0b34a754a9da"
    "3e550e1e0085d65707e98321a15543c8fe8fc80be3200a4ab79ec0fd0e5d5158d7"
)
PACKAGE_NAME = "com.invoxes.greenchain"

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ASSETS = os.path.normpath(os.path.join(HERE, "..", "tools", "assets"))

# ------------------------------------------------------------- secp256k1 -----
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8


def _inv(a, m):
    return pow(a, m - 2, m)


def _add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if p1 == p2:
        lam = (3 * x1 * x1) * _inv(2 * y1, P) % P
    else:
        lam = (y2 - y1) * _inv((x2 - x1) % P, P) % P
    x3 = (lam * lam - x1 - x2) % P
    return (x3, (lam * (x1 - x3) - y1) % P)


def _mul(k, point):
    result = None
    addend = point
    while k:
        if k & 1:
            result = _add(result, addend)
        addend = _add(addend, addend)
        k >>= 1
    return result


G = (GX, GY)


def ecdsa_verify_secp256k1(digest32: bytes, r: int, s: int, pub_uncompressed: bytes) -> bool:
    """ECDSASigner.verifySignature() semantics used by Secp256k1.java."""
    if not (1 <= r < N and 1 <= s < N):
        return False
    if len(pub_uncompressed) != 65 or pub_uncompressed[0] != 4:
        raise ValueError("public key is not a 65-byte uncompressed point")
    qx = int.from_bytes(pub_uncompressed[1:33], "big")
    qy = int.from_bytes(pub_uncompressed[33:65], "big")
    z = int.from_bytes(digest32, "big")
    w = _inv(s, N)
    u1 = z * w % N
    u2 = r * w % N
    point = _add(_mul(u1, G), _mul(u2, (qx, qy)))
    if point is None:
        return False
    return point[0] % N == r


def ecdsa_sign_secp256k1_rfc6979(digest32: bytes, priv: int):
    """ECDSA with RFC 6979 deterministic nonce (BouncyCastle's default ECDSASigner)."""
    import hmac

    z = int.from_bytes(digest32, "big")
    d = priv.to_bytes(32, "big")

    # RFC 6979, HMAC-SHA256, no extra entropy
    v = b"\x01" * 32
    k = b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + d + digest32, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + d + digest32, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        v = hmac.new(k, v, hashlib.sha256).digest()
        cand = int.from_bytes(v, "big")
        if 1 <= cand < N:
            break
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()

    kk = cand
    R = _mul(kk, G)
    r = R[0] % N
    s = (_inv(kk, N) * (z + r * priv)) % N
    # BouncyCastle emits low-s normalised signatures
    if s > N // 2:
        s = N - s
    return r, s


# ------------------------------------------------------------------- DER -----
def der_encode_signature(r: int, s: int) -> bytes:
    def enc_int(x):
        b = x.to_bytes((x.bit_length() + 7) // 8 or 1, "big")
        if b[0] & 0x80:
            b = b"\x00" + b
        return b"\x02" + bytes([len(b)]) + b

    body = enc_int(r) + enc_int(s)
    return b"\x30" + bytes([len(body)]) + body


def der_parse_signature(der: bytes):
    if der[0] != 0x30:
        raise ValueError("not a DER SEQUENCE")
    idx = 2
    out = []
    for _ in range(2):
        if der[idx] != 0x02:
            raise ValueError("expected DER INTEGER")
        ln = der[idx + 1]
        out.append(int.from_bytes(der[idx + 2: idx + 2 + ln], "big"))
        idx += 2 + ln
    return out[0], out[1]


# ------------------------------------------------------------------ AES ------
def aes_cbc_decrypt(key: bytes, iv: bytes, ct: bytes) -> bytes:
    """AES-CBC decrypt + PKCS#7 unpad (Java 'AES/CBC/PKCS5Padding' strips it for us;
    the `cryptography` low-level API does not, so we do it explicitly)."""
    d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = d.update(ct) + d.finalize()
    if not padded:
        raise ValueError("empty plaintext")
    pad = padded[-1]
    if not (1 <= pad <= 16) or padded[-pad:] != bytes([pad]) * pad:
        raise ValueError(f"bad PKCS#7 padding byte {pad}")
    return padded[:-pad]


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


# ------------------------------------------------------------------ chain ----
def load_assets(path):
    if os.path.isdir(path):
        base = path
    else:
        raise SystemExit(f"[!] assets dir not found: {path}")
    with open(os.path.join(base, "season.txt"), "rb") as f:
        season = f.read().decode("utf-8").strip()
    with open(os.path.join(base, "steward.dat"), "rb") as f:
        steward = f.read()
    with open(os.path.join(base, "flag.dat"), "rb") as f:
        flagblob = f.read()
    return season, steward, flagblob


def main():
    assets = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ASSETS
    season, steward, flagblob = load_assets(assets)

    print("=== [1] assets ===")
    print(f"season.txt  : {season!r}")
    print(f"steward.dat : {len(steward)} bytes")
    print(f"flag.dat    : {len(flagblob)} bytes")

    salt = SALT_PREFIX + season
    print(f"\n=== [2] key derivation ===")
    material = PACKAGE_NAME + salt
    print(f"material    : {material!r}")
    aes_key = sha256(material.encode("utf-8"))[:16]
    print(f"AES key     : {aes_key.hex()}")

    print("\n=== [3] recover steward private key ===")
    iv_s, ct_s = steward[:16], steward[16:]
    priv_plain = aes_cbc_decrypt(aes_key, iv_s, ct_s)
    priv_hex = priv_plain.decode("utf-8").strip()
    print(f"steward IV  : {iv_s.hex()}")
    print(f"plaintext   : {priv_hex!r}")
    priv = int(priv_hex, 16)
    assert 1 <= priv < N, "private key out of range"
    print(f"priv (int)  : {hex(priv)}")

    print("\n=== [4] derive + cross-check public key ===")
    pub = _mul(priv, G)
    pub_bytes = b"\x04" + pub[0].to_bytes(32, "big") + pub[1].to_bytes(32, "big")
    pub_hex = pub_bytes.hex()
    print(f"derived pub : {pub_hex}")
    print(f"APK pub     : {STEWARD_PUBKEY_HEX}")
    if pub_hex.lower() != STEWARD_PUBKEY_HEX.lower():
        raise SystemExit("[!] derived public key does NOT match the hard-coded one — chain is wrong")
    print("MATCH       : yes  (chain validated against the APK's own trust anchor)")

    print("\n=== [5] sign the claim message (what ClaimActivity verifies) ===")
    digest = sha256(CLAIM_MESSAGE.encode("utf-8"))
    print(f"sha256({CLAIM_MESSAGE!r}) = {digest.hex()}")
    r, s = ecdsa_sign_secp256k1_rfc6979(digest, priv)
    der = der_encode_signature(r, s)
    sig_hex = der.hex()
    print(f"r           : {hex(r)}")
    print(f"s           : {hex(s)}")
    print(f"DER sig hex : {sig_hex}")

    # independent verification of the produced signature
    rr, ss = der_parse_signature(der)
    ok = ecdsa_verify_secp256k1(digest, rr, ss, unhexlify(STEWARD_PUBKEY_HEX))
    print(f"verify sig  : {'PASS' if ok else 'FAIL'}")
    assert ok, "self-verification of the produced signature failed"

    print("\n=== [6] decrypt the flag ===")
    flag_key = sha256((priv_hex + "flag").encode("utf-8"))[:16]
    print(f"flag AES key: {flag_key.hex()}")
    iv_f, ct_f = flagblob[:16], flagblob[16:]
    flag_plain = aes_cbc_decrypt(flag_key, iv_f, ct_f)
    flag = flag_plain.decode("utf-8").strip()
    print(f"flag        : {flag}")

    with open(os.path.join(HERE, "signature.txt"), "w") as f:
        f.write(sig_hex + "\n")
    with open(os.path.join(HERE, "flag_recovered.txt"), "w") as f:
        f.write(flag + "\n")
    print(f"\n[saved] poc/signature.txt")
    print(f"[saved] poc/flag_recovered.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
