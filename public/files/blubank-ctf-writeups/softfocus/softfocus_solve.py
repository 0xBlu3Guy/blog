#!/usr/bin/env python3
"""Soft Focus — credential recovery from the published proof bundle.

Why this works
--------------
In prover.py the per-transcript blinding offsets are not independent random
vectors. They are derived from a single latent state of only two lanes:

    state   = (s_0, s_1)                 # two vectors of length `dimension`
    offset_i = route_i[0]*s_0 + route_i[1]*s_1

so every transcript hands us dimension scalar equations over the unknown
credential V and the 2*dimension latent state entries:

    z_i[j] = route_i[0]*s_0[j] + route_i[1]*s_1[j] + c_i*V[j]   (mod q)

For a fixed component j the three transcripts give a 3x3 linear system

    [ route_0[0] route_0[1] c_0 ] [ s_0[j] ]   [ z_0[j] ]
    [ route_1[0] route_1[1] c_1 ] [ s_1[j] ] = [ z_1[j] ]
    [ route_2[0] route_2[1] c_2 ] [  V[j]  ]   [ z_2[j] ]

which is invertible whenever the routes span (they do here), so the credential
falls straight out of public data.  The proof is perfectly sound as a proof and
leaks anyway -- the "no trace" claim dies on the randomness structure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier import (  # noqa: E402
    credential_digest,
    load_bundle,
    parse_bundle,
    transform_attachment,
)


def solve_mod(mat: list[list[int]], vec: list[int], q: int) -> list[int]:
    """Gaussian elimination over GF(q).  mat is n x n, returns x with mat*x=vec."""
    n = len(mat)
    a = [[mat[i][j] % q for j in range(n)] + [vec[i] % q] for i in range(n)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if a[r][col] % q), None)
        if pivot is None:
            raise ValueError("singular system -- routes do not span")
        a[col], a[pivot] = a[pivot], a[col]
        inv = pow(a[col][col], -1, q)
        a[col] = [(v * inv) % q for v in a[col]]
        for r in range(n):
            if r != col and a[r][col] % q:
                factor = a[r][col]
                a[r] = [(a[r][k] - factor * a[col][k]) % q for k in range(n + 1)]
    return [a[i][n] % q for i in range(n)]


def recover_credential(bundle_path: str | Path) -> tuple[list[int], "object"]:
    parsed = parse_bundle(load_bundle(bundle_path))
    q = parsed.q
    dimension = parsed.dimension
    transcripts = parsed.transcripts
    if len(transcripts) != 3:
        raise ValueError("this attack expects exactly three transcripts")

    # Sanity: each transcript must actually verify before we invert anything.
    for t in transcripts:
        lhs = 1
        for g, e in zip(parsed.generators, t.z):
            lhs = (lhs * pow(g, e, parsed.p)) % parsed.p
        rhs = (t.A * pow(parsed.commitment, t.challenge, parsed.p)) % parsed.p
        if lhs != rhs:
            raise ValueError(f"transcript {t.index} does not verify")

    matrix = [[t.route[0] % q, t.route[1] % q, t.challenge % q] for t in transcripts]

    credential: list[int] = []
    for j in range(dimension):
        rhs = [t.z[j] % q for t in transcripts]
        _s0, _s1, v = solve_mod(matrix, rhs, q)
        credential.append(v)
    return credential, parsed


def main(argv: list[str]) -> int:
    bundle_path = Path(argv[1]) if len(argv) > 1 else Path(
        "/home/kali/BlueCTF/SoftFocus/evidence/proof_bundle.json"
    )
    credential, parsed = recover_credential(bundle_path)

    # Independent check: re-derive the latent state and confirm every transcript's
    # z vector reproduces exactly.  Proves the recovered V is the real credential.
    q = parsed.q
    matrix = [[t.route[0] % q, t.route[1] % q, t.challenge % q] for t in parsed.transcripts]
    states = []
    for j in range(parsed.dimension):
        rhs = [t.z[j] % q for t in parsed.transcripts]
        states.append(solve_mod(matrix, rhs, q))
    for t in parsed.transcripts:
        for j in range(parsed.dimension):
            s0, s1, v = states[j]
            expect = (t.route[0] * s0 + t.route[1] * s1 + t.challenge * v) % q
            assert expect == t.z[j] % q, "reconstruction mismatch"

    cred_path = bundle_path.resolve().parent / "credential.json"
    cred_path.write_text(json.dumps(["%064x" % v for v in credential], indent=1))
    print("[+] credential written to " + str(cred_path))

    digest = credential_digest(credential, parsed.scalar_bytes)
    plaintext = transform_attachment(parsed.attachment, digest)

    print("[+] credential recovered (dimension %d):" % parsed.dimension)
    print("    " + " ".join("%064x" % v for v in credential))
    print("[+] credential_digest(sha256) = " + digest.hex())
    print("[+] attachment plaintext:")
    print("    " + repr(plaintext))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
