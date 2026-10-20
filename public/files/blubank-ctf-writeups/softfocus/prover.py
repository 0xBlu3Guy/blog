#!/usr/bin/env python3
"""Source-side implementation for the dropbox proof format."""

from __future__ import annotations

import json
from pathlib import Path
import secrets
import sys

from verifier import (
    challenge_scalar,
    commit_vector,
    element_hex,
    load_bundle,
    parse_bundle,
    scalar_hex,
)


def sample_scalars(length: int, q: int) -> list[int]:
    return [secrets.randbelow(q) for _ in range(length)]


def _apply_route(state: tuple[list[int], ...], route: tuple[int, ...], q: int) -> list[int]:
    return [
        sum(route[lane] * state[lane][column] for lane in range(len(state))) % q
        for column in range(len(state[0]))
    ]


def create_submission_proofs(
    parsed, credential: list[int], routes: list[tuple[int, ...]]
) -> dict:
    """Create the proof records attached to one upload session."""

    state = tuple(sample_scalars(parsed.dimension, parsed.q) for _ in range(2))
    commitment = commit_vector(parsed.generators, credential, parsed.p)
    transcripts = []

    for index, route in enumerate(routes):
        offset = _apply_route(state, route, parsed.q)
        A = commit_vector(parsed.generators, offset, parsed.p)
        c = challenge_scalar(
            parsed.domain,
            parsed.p,
            parsed.q,
            parsed.scalar_bytes,
            parsed.element_bytes,
            parsed.dimension,
            commitment,
            index,
            route,
            A,
            parsed.attachment,
        )
        z = [
            (offset_value + c * credential_value) % parsed.q
            for offset_value, credential_value in zip(offset, credential)
        ]
        transcripts.append(
            {
                "index": index,
                "route": [scalar_hex(value, parsed.scalar_bytes) for value in route],
                "A": element_hex(A, parsed.element_bytes),
                "z": [scalar_hex(value, parsed.scalar_bytes) for value in z],
            }
        )

    return {
        "commitment": element_hex(commitment, parsed.element_bytes),
        "transcripts": transcripts,
    }


def main(argv: list[str]) -> int:
    bundle_path = Path(argv[1]) if len(argv) > 1 else Path(__file__).with_name("proof_bundle.json")
    parsed = parse_bundle(load_bundle(bundle_path))
    routes = [item.route for item in parsed.transcripts]
    credential = sample_scalars(parsed.dimension, parsed.q)
    proof_records = create_submission_proofs(parsed, credential, routes)
    print(json.dumps(proof_records, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
