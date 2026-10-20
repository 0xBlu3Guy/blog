#!/usr/bin/env python3
"""Public verifier for the Soft Focus challenge."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Iterable


HASH_CHALLENGE_DOMAIN = b"soft-focus.challenge.v1"
HASH_GENERATOR_DOMAIN = b"soft-focus.generator.v1"
HASH_CREDENTIAL_DOMAIN = b"soft-focus.credential.v1"
HASH_ATTACHMENT_STREAM_DOMAIN = b"soft-focus.attachment.v1"

GROUP_P = int("f42ab87a7e738ece8b28638e6959be54ef57d89ef19c560a3daed493a7d555bb", 16)
GROUP_Q = int("7a155c3d3f39c767459431c734acdf2a77abec4f78ce2b051ed76a49d3eaaadd", 16)

HEX_RE = re.compile(r"^[0-9a-f]+$")
MAX_GENERATOR_DERIVATION_ATTEMPTS = 10_000


@dataclass(frozen=True)
class Transcript:
    index: int
    route: tuple[int, int]
    A: int
    z: tuple[int, ...]
    challenge: int


@dataclass(frozen=True)
class ParsedBundle:
    domain: str
    p: int
    q: int
    scalar_bytes: int
    element_bytes: int
    dimension: int
    generators: tuple[int, ...]
    commitment: int
    transcripts: tuple[Transcript, ...]
    attachment: bytes


def encode_int(value: int, width: int) -> bytes:
    if value < 0 or value >= 1 << (8 * width):
        raise ValueError("integer does not fit the requested width")
    return value.to_bytes(width, "big")


def scalar_hex(value: int, scalar_bytes: int) -> str:
    return encode_int(value, scalar_bytes).hex()


def element_hex(value: int, element_bytes: int) -> str:
    return encode_int(value, element_bytes).hex()


def _parse_hex_int(value: object, name: str) -> int:
    if not isinstance(value, str) or len(value) == 0 or len(value) % 2:
        raise ValueError(f"{name} must be an even-length lowercase hex string")
    if not HEX_RE.fullmatch(value):
        raise ValueError(f"{name} must use lowercase hex without 0x")
    return int(value, 16)


def _parse_fixed_hex(value: object, width: int, name: str) -> int:
    if not isinstance(value, str) or len(value) != 2 * width:
        raise ValueError(f"{name} must be {2 * width} hex characters")
    if not HEX_RE.fullmatch(value):
        raise ValueError(f"{name} must use lowercase hex without 0x")
    return int(value, 16)


def _parse_scalar(value: object, q: int, scalar_bytes: int, name: str) -> int:
    scalar = _parse_fixed_hex(value, scalar_bytes, name)
    if scalar >= q:
        raise ValueError(f"{name} is not canonical modulo q")
    return scalar


def _parse_group_element(value: object, p: int, q: int, element_bytes: int, name: str) -> int:
    element = _parse_fixed_hex(value, element_bytes, name)
    if not 1 < element < p - 1:
        raise ValueError(f"{name} is outside the accepted group range")
    if pow(element, q, p) != 1:
        raise ValueError(f"{name} is not in the order-q subgroup")
    return element


def _hash_len_prefixed(hasher: "hashlib._Hash", data: bytes) -> None:
    hasher.update(len(data).to_bytes(4, "big"))
    hasher.update(data)


def derive_generators(domain: str, dimension: int, p: int, q: int) -> tuple[int, ...]:
    """Derive independent-looking generators in the quadratic-residue subgroup."""

    if p != 2 * q + 1:
        raise ValueError("expected a safe-prime group with p = 2q + 1")

    element_bytes = (p.bit_length() + 7) // 8
    generators: list[int] = []
    seen: set[int] = set()
    counter = 0

    while len(generators) < dimension:
        if counter >= MAX_GENERATOR_DERIVATION_ATTEMPTS:
            raise ValueError("could not derive enough distinct generators")
        seed = HASH_GENERATOR_DOMAIN + domain.encode() + len(generators).to_bytes(4, "big")
        seed += counter.to_bytes(4, "big")
        candidate = int.from_bytes(hashlib.shake_256(seed).digest(element_bytes + 16), "big") % p
        counter += 1
        if candidate <= 1 or candidate >= p - 1:
            continue
        generator = pow(candidate, 2, p)
        if generator == 1 or generator in seen:
            continue
        if pow(generator, q, p) != 1:
            continue
        seen.add(generator)
        generators.append(generator)

    return tuple(generators)


def commit_vector(generators: Iterable[int], vector: Iterable[int], p: int) -> int:
    acc = 1
    for generator, exponent in zip(generators, vector):
        acc = (acc * pow(generator, exponent, p)) % p
    return acc


def challenge_scalar(
    domain: str,
    p: int,
    q: int,
    scalar_bytes: int,
    element_bytes: int,
    dimension: int,
    commitment: int,
    index: int,
    route: tuple[int, int],
    A: int,
    attachment: bytes,
) -> int:
    hasher = hashlib.sha256()
    hasher.update(HASH_CHALLENGE_DOMAIN)
    _hash_len_prefixed(hasher, domain.encode())
    hasher.update(encode_int(p, element_bytes))
    hasher.update(encode_int(q, scalar_bytes))
    hasher.update(dimension.to_bytes(4, "big"))
    hasher.update(encode_int(commitment, element_bytes))
    hasher.update(index.to_bytes(4, "big"))
    for value in route:
        hasher.update(encode_int(value, scalar_bytes))
    hasher.update(encode_int(A, element_bytes))
    _hash_len_prefixed(hasher, attachment)
    return int.from_bytes(hasher.digest(), "big") % q


def load_bundle(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_bundle(bundle: dict) -> ParsedBundle:
    if not isinstance(bundle, dict):
        raise ValueError("bundle must be a JSON object")
    if bundle.get("name") != "soft-focus" or bundle.get("version") != 1:
        raise ValueError("unexpected challenge name or version")

    domain = bundle.get("domain")
    if not isinstance(domain, str) or not domain:
        raise ValueError("domain must be a non-empty string")

    group = bundle.get("group")
    if not isinstance(group, dict):
        raise ValueError("group must be an object")
    p = _parse_hex_int(group.get("p"), "group.p")
    q = _parse_hex_int(group.get("q"), "group.q")
    if p != GROUP_P or q != GROUP_Q:
        raise ValueError("group parameters do not match the fixed challenge group")
    if p != 2 * q + 1:
        raise ValueError("group parameters are not a safe-prime pair")
    scalar_bytes = group.get("scalar_bytes")
    element_bytes = group.get("element_bytes")
    if scalar_bytes != (q.bit_length() + 7) // 8:
        raise ValueError("scalar_bytes does not match q")
    if element_bytes != (p.bit_length() + 7) // 8:
        raise ValueError("element_bytes does not match p")
    if len(group["p"]) != 2 * element_bytes or len(group["q"]) != 2 * scalar_bytes:
        raise ValueError("group integers are not fixed-width encoded")

    dimension = bundle.get("dimension")
    if not isinstance(dimension, int) or dimension <= 0 or dimension > 64:
        raise ValueError("dimension must be a small positive integer")

    generators_json = bundle.get("generators")
    if not isinstance(generators_json, list) or len(generators_json) != dimension:
        raise ValueError("generator count does not match dimension")
    generators = tuple(
        _parse_group_element(value, p, q, element_bytes, f"generators[{i}]")
        for i, value in enumerate(generators_json)
    )
    expected_generators = derive_generators(domain, dimension, p, q)
    if generators != expected_generators:
        raise ValueError("generators do not match the deterministic derivation")

    commitment = _parse_group_element(bundle.get("commitment"), p, q, element_bytes, "commitment")

    attachment_json = bundle.get("attachment")
    if not isinstance(attachment_json, dict) or attachment_json.get("format") != "credential-stream-v1":
        raise ValueError("missing attachment metadata")
    attachment_hex = attachment_json.get("data")
    if not isinstance(attachment_hex, str) or len(attachment_hex) % 2 or not HEX_RE.fullmatch(
        attachment_hex
    ):
        raise ValueError("attachment data must be lowercase hex")
    attachment = bytes.fromhex(attachment_hex)
    if not attachment:
        raise ValueError("attachment must not be empty")

    transcripts_json = bundle.get("transcripts")
    if not isinstance(transcripts_json, list) or len(transcripts_json) != 3:
        raise ValueError("expected exactly three transcripts")

    transcripts: list[Transcript] = []
    for expected_index, item in enumerate(transcripts_json):
        if not isinstance(item, dict):
            raise ValueError(f"transcripts[{expected_index}] must be an object")
        index = item.get("index")
        if index != expected_index:
            raise ValueError("transcript indices must be 0, 1, 2")
        route_json = item.get("route")
        if not isinstance(route_json, list) or len(route_json) != 2:
            raise ValueError(f"transcripts[{index}].route must contain two scalars")
        route = tuple(
            _parse_scalar(value, q, scalar_bytes, f"transcripts[{index}].route[{position}]")
            for position, value in enumerate(route_json)
        )
        A = _parse_group_element(item.get("A"), p, q, element_bytes, f"transcripts[{index}].A")
        z_json = item.get("z")
        if not isinstance(z_json, list) or len(z_json) != dimension:
            raise ValueError(f"transcripts[{index}].z has wrong length")
        z = tuple(
            _parse_scalar(value, q, scalar_bytes, f"transcripts[{index}].z[{j}]")
            for j, value in enumerate(z_json)
        )
        c = challenge_scalar(
            domain,
            p,
            q,
            scalar_bytes,
            element_bytes,
            dimension,
            commitment,
            index,
            route,
            A,
            attachment,
        )
        transcripts.append(Transcript(index, route, A, z, c))

    return ParsedBundle(
        domain=domain,
        p=p,
        q=q,
        scalar_bytes=scalar_bytes,
        element_bytes=element_bytes,
        dimension=dimension,
        generators=generators,
        commitment=commitment,
        transcripts=tuple(transcripts),
        attachment=attachment,
    )


def verify_parsed(parsed: ParsedBundle) -> bool:
    for transcript in parsed.transcripts:
        lhs = commit_vector(parsed.generators, transcript.z, parsed.p)
        rhs = (transcript.A * pow(parsed.commitment, transcript.challenge, parsed.p)) % parsed.p
        if lhs != rhs:
            return False
    return True


def verify_bundle(bundle: dict) -> bool:
    return verify_parsed(parse_bundle(bundle))


def credential_digest(credential: Iterable[int], scalar_bytes: int) -> bytes:
    hasher = hashlib.sha256()
    hasher.update(HASH_CREDENTIAL_DOMAIN)
    for value in credential:
        hasher.update(encode_int(value, scalar_bytes))
    return hasher.digest()


def transform_attachment(data: bytes, digest: bytes) -> bytes:
    stream = hashlib.shake_256(HASH_ATTACHMENT_STREAM_DOMAIN + digest).digest(len(data))
    return bytes(a ^ b for a, b in zip(data, stream))


def main(argv: list[str]) -> int:
    bundle_path = Path(argv[1]) if len(argv) > 1 else Path(__file__).with_name("proof_bundle.json")
    try:
        parsed = parse_bundle(load_bundle(bundle_path))
        if not verify_parsed(parsed):
            print("FAIL: proof bundle does not verify")
            return 1
    except Exception as exc:  # noqa: BLE001 - public verifier should print parse errors.
        print(f"FAIL: {exc}")
        return 1

    print("OK: proof bundle verifies")
    print(f"dimension: {parsed.dimension}")
    print(f"transcripts: {len(parsed.transcripts)}")
    print(f"attachment bytes: {len(parsed.attachment)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
