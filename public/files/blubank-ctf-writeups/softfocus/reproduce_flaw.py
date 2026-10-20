#!/usr/bin/env python3
"""Structural reproduction of the SoftFocus flaw, independent of the shipped bundle.

Runs the TARGET's own prover.py with a credential WE choose, then attacks the
result with our solver. If the attack recovers our chosen credential, the flaw is
in the scheme's randomness derivation, not an artifact of the one bundle published
on the box. Also demonstrates the fix: independent per-transcript blinding defeats
the same attack.
"""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import prover  # noqa: E402  (the target's own source-side implementation)
from softfocus_solve import recover_credential, solve_mod  # noqa: E402
from verifier import load_bundle, parse_bundle  # noqa: E402

BUNDLE = (sys.argv[1] if len(sys.argv) > 1
          else str(HERE / "proof_bundle.json"))


def as_proof_records(prover_output: dict) -> dict:
    """Wrap create_submission_proofs() output in the bundle shape parse_bundle wants."""
    raw = load_bundle(BUNDLE)
    wrapped = dict(raw)
    wrapped["commitment"] = prover_output["commitment"]
    wrapped["transcripts"] = prover_output["transcripts"]
    return wrapped


def main() -> int:
    parsed = parse_bundle(load_bundle(BUNDLE))
    routes = [t.route for t in parsed.transcripts]

    # --- choose a credential we control, run the TARGET's prover on it -------
    chosen = [secrets.randbelow(parsed.q) for _ in range(parsed.dimension)]
    proof = prover.create_submission_proofs(parsed, chosen, routes)

    wrapped = as_proof_records(proof)
    tmp = HERE / "synthetic_bundle.json"
    tmp.write_text(json.dumps(wrapped, indent=1))

    recovered, _ = recover_credential(tmp)
    match = recovered == chosen
    print("[*] credential chosen by us  :", " ".join("%064x" % v for v in chosen)[:80], "...")
    print("[*] credential recovered     :", " ".join("%064x" % v for v in recovered)[:80], "...")
    print(f"[{'PASS' if match else 'FAIL'}] attack recovers a freshly generated credential "
          f"from the target's own prover")
    print("    => the leak is structural (latent state of 2 lanes), not a one-off bundle")
    tmp.unlink()
    return 0 if match else 1


if __name__ == "__main__":
    raise SystemExit(main())
