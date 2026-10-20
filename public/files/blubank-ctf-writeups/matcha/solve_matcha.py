#!/usr/bin/env python3
"""
Matcha (BlueCTF) - full solver.

Recovers the algorithm from the stripped binary `matcha` and decrypts `flag.enc`.

Recovered algorithm (see ../results.md and ../WRITEUP.md for the disassembly evidence):

  1. The binary reads `flag.txt` (up to 0x100 bytes) into a stack buffer.
     If the last byte read is '\n' it is dropped. An empty/short read is an error path.

  2. The buffer is processed 8 bytes at a time (blocks). For block index i:

        edi = (0xffffffa3 - 8*i) & 0xffffffff          # per-block seed, low byte used
        S   = 0
        for j in range(8):
            k  = edi & 0xff
            S |= ((chunk[j] ^ k) & 0xff) << (8*j)      # little-endian assembly
            edi = (edi + 0x5f) & 0xffffffff

  3. The modulus comes from a self-modifying 128-bit routine with the literal key
     0x7c11472b66a24399 stored in .bss. On first call the "encrypt" flag is set from
     zero, the key is derived (rot13-style mixing with 0x9e3779b97f4a7c15) and stored
     back BEFORE the value is used -- so the key used by both the encrypt branch and
     the decrypt branch is the same fixed constant:

        D = 0x7c11472b66a24399

  4. Each block is encrypted with the RSA shape

        ct = (S mod D) ** 65537 mod D            # 0x10001 = 65537, hard-coded

     and printed as "%016llx\n".

  5. D is composite and small enough to factor, so the trapdoor inverts:

        D = 3712189883 * 2408283323

     The "too much confidence" is a 63-bit RSA modulus.

Usage:  python3 solve_matcha.py [flag.enc]      (default: ../challenge/matcha/flag.enc)
"""

import sys
import os
import math

# ---------------------------------------------------------------- constants --
D_DEFAULT = 0x7C11472B66A24399          # modulus, from the 128-bit div routine key
E = 0x10001                             # 65537, hard-coded public exponent
SEED_BASE = 0xFFFFFFA3                  # edi seed for block 0 (low byte 0xa3)
STEP = 0x5F                             # per-byte increment of edi

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ENC = os.path.join(HERE, "..", "challenge", "matcha", "flag.enc")


# ------------------------------------------------------------ byte transform --
def seeds_for_block(block_index):
    """Return the 8 per-byte XOR keys used for the given block index."""
    edi = (SEED_BASE - 8 * block_index) & 0xFFFFFFFF
    keys = []
    for _ in range(8):
        keys.append(edi & 0xFF)
        edi = (edi + STEP) & 0xFFFFFFFF
    return keys


def block_to_S(chunk, block_index):
    """Plaintext chunk (<=8 bytes) -> the 64-bit integer S fed to the RSA step."""
    S = 0
    for j, k in enumerate(seeds_for_block(block_index)):
        if j < len(chunk):
            S |= ((chunk[j] ^ k) & 0xFF) << (8 * j)
    return S


def S_to_block(S, block_index):
    """Inverse of block_to_S: integer S -> 8 plaintext bytes."""
    out = bytearray()
    for j, k in enumerate(seeds_for_block(block_index)):
        out.append(((S >> (8 * j)) & 0xFF) ^ k)
    return bytes(out)


# ------------------------------------------------------------------ encrypt --
def encrypt(pt, D=D_DEFAULT, block_index=0):
    """Reference re-implementation of the binary's encryption. Returns hex strings."""
    res = []
    for i in range(0, len(pt), 8):
        S = block_to_S(pt[i:i + 8], block_index + i // 8)
        res.append("%016x" % pow(S % D, E, D))
    return res


# ------------------------------------------------------------------ decrypt --
def factor_D(D=D_DEFAULT):
    """Factor the modulus. D is a 63-bit semiprime -> trivial to break."""
    # p, q produced by integer factorisation of D (see results.md for evidence)
    p, q = 3712189883, 2408283323
    assert p * q == D, "factorisation does not reproduce D"
    return p, q


def private_exponent(D=D_DEFAULT, e=E):
    p, q = factor_D(D)
    lam = (p - 1) * (q - 1) // math.gcd(p - 1, q - 1)     # Carmichael
    assert math.gcd(e, lam) == 1, "e not invertible mod lambda(D)"
    return pow(e, -1, lam), p, q


def decrypt_block(ct, d, D=D_DEFAULT):
    """
    Invert one ciphertext value. Returns (candidates, n) where candidates are the
    possible S values and n is the number of significant bytes in the block.

    Because the binary reduces S modulo D before the exponentiation, the true S is
    m or m + D (S is < 2**64 and D is ~2**63, so at most one wrap).

    n comes from bit_length(m): the binary ORs each plaintext byte into S without
    clearing the buffer, so for a short final block S keeps stale stack bytes in its
    upper positions. The leading zero bytes of m are exactly those positions, so
    (m.bit_length()+7)//8 is the real length of the final chunk. For full blocks n == 8.
    """
    m = pow(ct, d, D)
    cands = [m]
    if m + D < (1 << 64):
        cands.append(m + D)
    n = max(1, (m.bit_length() + 7) // 8)
    return cands, n


def decrypt(hexlines, D=D_DEFAULT):
    d, p, q = private_exponent(D)
    print("[*] modulus   D = %d (0x%016x), %d bits" % (D, D, D.bit_length()))
    print("[*] factored  D = %d * %d" % (p, q))
    print("[*] exponent  d = %d" % d)
    print()

    blocks = []
    for idx, line in enumerate(hexlines):
        ct = int(line, 16)
        cands, n = decrypt_block(ct, d, D)
        raw = [S_to_block(S, idx) for S in cands]
        blocks.append((ct, raw, n))
        print("[*] block %d ct=%016x -> S candidates %s (chunk len %d)" %
              (idx, ct, ", ".join("%016x" % c for c in cands), n))
        for r in raw:
            print("        %r" % r[:n])

    return blocks


# ------------------------------------------------------------------- verify --
def verify(blocks, hexlines, D=D_DEFAULT):
    """
    Re-encrypt each recovered plaintext block and compare to the ciphertext.

    NOTE: this confirms the RSA inversion only. Because the binary reduces S mod D
    before exponentiating, BOTH m and m+D re-encrypt back to the same ciphertext, so
    this check cannot discriminate between the two candidates -- text plausibility
    does that. It DOES catch a wrong private exponent / wrong modulus.
    """
    ok = True
    for idx, (ct, raws, n) in enumerate(blocks):
        matched = False
        for r in raws:
            if int(encrypt(r[:n], D, block_index=idx)[0], 16) == ct:
                matched = True
                break
        if not matched:
            ok = False
            print("[!] block %d FAILED re-encryption check" % idx)
    return ok


# --------------------------------------------------------------------- main --
def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ENC
    with open(path) as fh:
        hexlines = [l.strip() for l in fh if l.strip()]
    print("[*] %d ciphertext blocks from %s\n" % (len(hexlines), path))

    blocks = decrypt(hexlines)

    # Candidate selection: S and S+D both re-encrypt to the same ct, so the RSA
    # inversion alone cannot choose. Pick the candidate that is printable ASCII
    # (the flag is a text file). Both are tried when ambiguous.
    def score(raw):
        return sum(1 for b in raw if 0x20 <= b < 0x7F)

    print()
    chosen = []
    for idx, (ct, raws, n) in enumerate(blocks):
        best = max(raws, key=lambda r: score(r[:n]))
        if score(best[:n]) == 0:
            best = raws[0]
        chosen.append(best[:n])
        other = [r[:n] for r in raws if r is not best]
        if other and score(best[:n]) > score(other[0]):
            print("[*] block %d: chose %r over %r" % (idx, best[:n], other[0]))

    pt = b"".join(chosen)
    print()
    print("[+] recovered plaintext bytes: %r" % pt)

    text = pt.decode("utf-8", "replace")
    print("[+] recovered flag: %s" % text)

    # Independent check: feed the plaintext back through the real binary shape.
    reenc = []
    for i in range(0, len(pt), 8):
        reenc.append(int(encrypt(pt[i:i + 8], block_index=i // 8)[0], 16))
    original = [int(l, 16) for l in hexlines]
    print()
    print("[*] re-encryption of recovered plaintext matches flag.enc: %s" %
          (reenc == original))

    return text


if __name__ == "__main__":
    main()
