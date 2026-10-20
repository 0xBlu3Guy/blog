---
title: "Writeups for some of the BluBank CTF challenges"
description: "Four BluBank CTF writeups: 19-digit RSA in a stripped binary, an Android vault that encrypts its own key, and a zero-knowledge proof that leaks."
date: 2026-10-20
tags:
  - CTF
---

BluBank, one of Iran's large banks, ran its CTF on Wednesday, 16 September 2026,
with challenges across reversing, cryptography, mobile and web. I took part, and
these are writeups for four of the challenges I solved: `Matcha`, `GreenChain`,
`SoftFocus`, and a second instance of `SoftFocus`. They have almost nothing in
common mechanically. One is a stripped x86-64 binary doing RSA with a modulus
small enough to factor on a laptop. One is an Android app that encrypts its own
trust anchor under a key derived from its package name. One is a zero-knowledge
proof bundle that hides an eight-component secret behind three transcripts, which
turns out to be barely enough equations.

The flags are all stale now, so I can write them up with the actual values in
place. Two of the four needed no network at all, and the two web ones needed four
requests each.

> [!NOTE] Disclosure
> These challenges were solved with the help of AI. I set up the workspace and the
> rules the work ran under, and I checked the evidence behind every flag before
> recording it, but the reversing, the cryptanalysis and most of the scripts in
> these writeups were produced with AI assistance.

| Challenge | Type | Flag |
|---|---|---|
| Matcha | reversing + crypto, local binary | `BDD{03d5a29801f0f97e40d84e83eb53562d}` |
| GreenChain | Android reversing + crypto | `BDD{steward_signed_the_green_chain}` |
| SoftFocus | crypto, broken zero-knowledge prover | `BDD{7ace6e3cf983d3b205de1dc3f2dd59af53f133981d8f5fe10b30df54dad1d4a1}` |
| SoftFocus (second instance) | same, fresh secrets | `BDD{43b4507edae2809cb031d7fd8b6ee9bff67d7b46fb5ac3143231a89bfabdd590}` |

## Matcha: RSA with a 19-digit modulus

The archive held two files:

```text
matcha     ELF 64-bit LSB pie executable, x86-64, stripped, dynamically linked, 14528 bytes
flag.enc   ASCII text, 5 lines of 16 hex characters
```

`strings` told me the shape of the program before I opened a disassembler:
`fopen`, `fread`, `fwrite`, the literals `flag.txt` and `flag.enc`, and the format
string `%016llx`. It reads a plaintext flag, encrypts it, and writes one 64-bit
value per line. Five lines mean five blocks of 8 bytes, so the flag is between 33
and 40 bytes.

`.text` is 0x621 bytes. At that size the whole program is readable by hand, so
that is what I did: `objdump -d -M intel` into a file, `readelf -h` for the entry
point. `_start` at `0x14a0` ends in a `lea` into `main` at `0x1100`.

### The block function

Inside `main`, the round function at `0x1290` runs once per 8-byte block:

```asm
1290  mov edi, 0xffffffa3
1299  sub edi, r13d                  ; edi = (0xffffffa3 - 8*block_index) & 0xffffffff
12cb  movzx edx, BYTE PTR [r14+rax]  ; plaintext byte
12d0  lea ecx, [rax*8]               ; shift = 8*j
12db  xor edx, edi                   ; XOR with low byte of edi
12dd  add edi, 0x5f                  ; edi += 0x5f   (rolling key)
12e3  shl rdx, cl
12e6  or  rsi, rdx                   ; little-endian assembly into S
12e9  cmp rax, 8 ; jne 12c0          ; 8 bytes per block
```

The key byte starts at `0xa3` and advances by `0x5f` for every byte, so the mask
changes inside a block as well as between blocks. Then `S` goes through a
square-and-multiply loop with the exponent `0x10001` (65537, visible in two
places), against the modulus `0x7c11472b66a24399`:

```asm
12f4  mov r12d, 0x11                 ; 17-bit loop counter
12fa  mov ebp, 0x10001               ; 65537
131f  movabs rax, 0x7c11472b66a24399 ; modulus
1329  imul rax, r15
132d  sub rsi, rax                   ; rsi = S mod D
1330  cmp QWORD PTR [rip+0x2d10], 0  ; zero-initialised flag
1338  cmove rbx, rsi                 ; first use: key = S mod D
```

That is textbook RSA encryption of each block, with a public exponent of 65537
and a modulus that is 63 bits long. There is a key-derivation chain earlier in
`main` that mixes a `.data` word (`0xc0ffee00cafebabe`) with the golden-ratio
constant and writes the result back to memory. It is decorative: the value is
overwritten before it reduces anything, and the modulus actually used is the
literal in `.text`. I confirmed that empirically rather than by staring at it,
which is the next section.

### Proving the model before breaking it

A disassembly reading is a hypothesis until it predicts something. The binary
itself is the best oracle I had, so I copied it into a scratch directory and ran
it against chosen inputs, never touching the original `flag.enc`:

```console
$ printf 'AAAABBBBCCCCDDDDEEEE' > flag.txt && ./matcha && cat flag.enc
1a630a78d52245da
6d417c9b413fb730
2ac5f8285adf5e64
```

A Python re-implementation of the reading above reproduces both that output and a
second test vector exactly. My first model ignored the per-byte rolling key and
failed this test, which is how the correct reading was forced. That failure is in
my notes and it is worth keeping: the model was wrong, the oracle said so, and the
oracle cost thirty seconds to run.

### Factoring the locked box

```
D = 0x7c11472b66a24399 = 8940004987038221209
  = 3712189883 * 2408283323
lambda(D) = lcm(p-1, q-1)
d = e^-1 mod lambda(D) = 4109671331615865757
```

Both factors are around 2^31. A full RSA implementation with a 19-digit modulus
is the joke of the challenge, and it means the "untouchable" cipher in the blurb
is invertible with `pow` and a factoring tool.

One detail nearly cost me the last block. The binary reduces `S mod D` before
exponentiating, so the ciphertext is invariant under `S -> S + D`, and decrypting
returns `m = S mod D`. The true `S` is either `m` or `m + D`, and **both
re-encrypt to the identical ciphertext**, so a round-trip check cannot tell them
apart. Picking the printable ASCII candidate does, and in every block of
`flag.enc` exactly one of the two candidates is text. The final block also has
three leading zero bytes in `m`, because the buffer is not cleared before the
short block is assembled, which is what says the real chunk is 5 bytes and not 8:

```python
import math
D = 0x7c11472b66a24399
e = 65537
p, q = 3712189883, 2408283323
lam = (p-1)*(q-1)//math.gcd(p-1, q-1)
d = pow(e, -1, lam)

def unkey(S, i, n):
    edi = (0xffffffa3 - 8*i) & 0xffffffff
    out = bytearray()
    for j in range(n):
        out.append(((S >> (8*j)) & 0xff) ^ (edi & 0xff))
        edi = (edi + 0x5f) & 0xffffffff
    return bytes(out)

out = b""
for i, line in enumerate(open("flag.enc")):
    c = int(line, 16)
    m = pow(c, d, D)
    n = max(1, (m.bit_length() + 7) // 8)
    out += max((unkey(S, i, n) for S in (m, m+D)),
               key=lambda r: sum(0x20 <= b < 0x7f for b in r))
print(out.decode())
```

### Getting and testing the flag

The challenge files are here: [matcha](/blog/files/blubank-ctf-writeups/matcha/matcha)
(14 KB), [flag.enc](/blog/files/blubank-ctf-writeups/matcha/flag.enc) (85 B), and
[solve_matcha.py](/blog/files/blubank-ctf-writeups/matcha/solve_matcha.py) (8 KB),
which is the solver written out as a script.

1. Keep the original `flag.enc` untouched.
2. Confirm the shape: `file`, `strings -n 5`.
3. Disassemble, find `main`, read the round function and the constants.
4. Test the model against the real binary with a chosen input.
5. Factor `D`, invert `e`, and run the solver.

```bash
# 1-3
cp flag.enc flag.enc.orig && chmod +x matcha
strings -n 5 matcha | tail -8
objdump -d -M intel matcha > matcha.disasm.txt

# 4: known-answer test, then check the model reproduces it
printf 'AAAABBBBCCCCDDDDEEEE' > flag.txt && ./matcha && cat flag.enc

# 5: factor and decrypt
python3 solve_matcha.py flag.enc
# BDD{03d5a29801f0f97e40d84e83eb53562d}
```

The test is the part I care about. The recovered plaintext goes back into the
**unmodified challenge binary**:

```console
$ printf 'BDD{03d5a29801f0f97e40d84e83eb53562d}' > flag.txt
$ ./matcha
$ diff flag.enc flag.enc.orig && echo IDENTICAL
IDENTICAL
```

That check does not involve my solver at all. The binary that made the ciphertext
regenerates it byte-for-byte from the flag I claim it contains, which is about as
close to proof as a reversing challenge allows.

## GreenChain: an Android vault that ships its own key

`GreenChain.apk`, package `com.invoxes.greenchain`, with exactly one permission,
and it is AndroidX's auto-generated local receiver permission. No
`android.permission.INTERNET`. The whole challenge is offline, and no emulator or
device was needed.

The APK has five dex files. `classes.dex` is 11 MB of AndroidX and `classes2.dex`
is 514 KB of Material. The challenge lives in the small ones: `classes3.dex`
(6.6 KB) and `classes4.dex` (10.4 KB), which decompile to five classes total.
Starting from the smallest dex files is the shortcut here, and it saves reading
11 MB of library code looking for something that was never there.

Three assets carry the whole puzzle:

```text
assets/season.txt    4 bytes   "2026"
assets/steward.dat  96 bytes
assets/flag.dat     64 bytes
```

96 bytes is a 16-byte IV plus 80 bytes of ciphertext, five AES blocks. 64 bytes is
16 plus 48, three blocks. Both blobs are IV-prefixed AES-CBC, which the
decompiled `StewardVault` confirms.

### The app verifies, it never signs

`StewardClaim.verifyAndUnlock()` checks a signature against a hard-coded public
key, and only then decrypts the flag:

```java
byte[] digest = StewardVault.claimMessageDigest();          // SHA256("greenchain-claim:v1")
boolean valid = Secp256k1.verifyClaimSignature(digest, signatureHex,
                                               StewardVault.STEWARD_PUBKEY_HEX);
if (!valid) return Result.fail("Invalid steward signature.");
String privHex = StewardVault.decryptStewardPrivateKeyHex(context);
String flag    = StewardVault.decryptFlag(context, privHex);
return Result.ok(flag);
```

The signature check looks like the barrier. It is not, because the private key
that satisfies it is shipped inside the APK, encrypted under a key derived
entirely from public constants:

```java
String material = c.getPackageName() + buildSalt(c);   // "com.invoxes.greenchain" + "eco-2026"
byte[] digest   = sha256(material.getBytes(UTF_8));
byte[] key      = Arrays.copyOf(digest, 16);
```

The package name is in the manifest, `eco-` is a literal in the source, and the
season ships in `assets/season.txt`. So:

| Derivation | Value |
|---|---|
| salt | `eco-2026` |
| AES-128 key for `steward.dat` | `SHA256("com.invoxes.greenchaineco-2026")[:16]` = `90034cebb6a7868d233884eedb45d723` |
| decrypted steward key | `d92b206f1525872e69988c816811f57c6085978e3aa37013baf956adaf8ab5fe` |
| AES-128 key for `flag.dat` | `SHA256(steward_hex + "flag")[:16]` = `4ff5baa7f6db11fb0883c1553eba510d` |

### The check that makes this airtight

Decrypting something to a plausible-looking string is not proof that I found the
right key. The proof here is a cryptographic identity check: derive the secp256k1
public key from the recovered private key and compare it to the constant the app
trusts.

```
derived pub : 041c44e3f125897027892cd90ae3b4246ad4c65a99bccdf3cd3f0b34a754a9da
              3e550e1e0085d65707e98321a15543c8fe8fc80be3200a4ab79ec0fd0e5d5158d7
APK pub     : 041c44e3f125897027892cd90ae3b4246ad4c65a99bccdf3cd3f0b34a754a9da
              3e550e1e0085d65707e98321a15543c8fe8fc80be3200a4ab79ec0fd0e5d5158d7
MATCH       : yes
```

Exact match. The key recovered from the asset is the steward key the app trusts,
not a key that happens to decrypt something.

### Getting and testing the flag

The files are here: [GreenChain.apk](/blog/files/blubank-ctf-writeups/greenchain/GreenChain.apk)
(9.6 MB) and [greenchain_solve.py](/blog/files/blubank-ctf-writeups/greenchain/greenchain_solve.py)
(10 KB). The APK is the challenge artifact itself, unmodified.

1. Read the manifest: package name, SDK, permissions.
2. Unpack the dex files and the assets.
3. Decompile the two small dex files and read `StewardVault` / `StewardClaim`.
4. Derive the AES key from the package name and the season, decrypt
   `steward.dat` to get the private key.
5. Confirm that key against the hard-coded public key.
6. Derive the flag key from the private key and decrypt `flag.dat`.

```bash
# 1-2
aapt dump badging GreenChain.apk | head -3
aapt dump permissions GreenChain.apk
unzip -o GreenChain.apk 'classes*.dex' 'assets/*' -d gc

# 3: jadx wants ABSOLUTE paths and a non-existent output dir
jadx -d gc/src3 --no-res "$PWD/gc/classes3.dex"
jadx -d gc/src4 --no-res "$PWD/gc/classes4.dex"

# 4-6
python3 greenchain_solve.py gc/assets
# BDD{steward_signed_the_green_chain}
```

Two `jadx` details cost me time. It resolves relative APK paths against its own
install directory, so the APK argument has to be absolute. It also wants to create
its output directory itself, so a `mkdir -p` beforehand fails with `Can't create
directory .../sources`.

The flag was decrypted a second time with the **OpenSSL CLI** rather than my
solver, so a bug in my own AES code could not produce a false positive:

```console
$ openssl enc -d -aes-128-cbc -K 4ff5baa7f6db11fb0883c1553eba510d \
        -iv $(xxd -p /tmp/fiv.bin) -in /tmp/fct.bin
BDD{steward_signed_the_green_chain}
```

The lesson is not subtle. A derivation whose every input is public is obfuscation
wearing the word "encryption", and a trust anchor that ships the private half of
itself is not a trust anchor. The app asks the player to earn trust with a
signature, and then hands over the signing key inside the box.

## SoftFocus: three transcripts, two lanes of randomness

The target was not a web application. It was a directory listing from
`SimpleHTTP/0.6 Python/3.11.16` serving three files: `proof_bundle.json`,
`prover.py`, `verifier.py`. "The evidence is on your desk" is literal. I sent four
requests in total, one second apart, and the whole challenge was offline after
that.

The scheme is a Pedersen vector commitment plus a Schnorr-style proof of knowledge
over a fixed safe-prime group, with `p = 2q + 1`, 256-bit parameters and
`dimension = 8`:

```
commitment = prod_j generators[j] ** credential[j]   (mod p)
A[i]       = prod_j generators[j] ** offset[i][j]    (mod p)
z[i][j]    = offset[i][j] + c[i] * credential[j]     (mod q)
verify:  prod_j generators[j] ** z[i][j] == A[i] * commitment ** c[i]   (mod p)
```

The challenges `c[i]` are Fiat-Shamir hashes binding the parameters, the
commitment, the transcript index, the route, `A`, and the attachment. Those
bindings are all present and correct. The verifier accepts the published bundle,
so this is not a tampered-bundle challenge. The proof is sound.

The secret is not behind an endpoint. The bundle carries a 69-byte attachment
masked with a keystream keyed only by the credential:

```python
digest = sha256(b"soft-focus.credential.v1" || credential[j] as 32-byte big-endian each)
keystream = shake_256(b"soft-focus.attachment.v1" || digest).digest(len(attachment))
plaintext = attachment XOR keystream
```

Recover the credential and the flag falls out. So the question is whether the
proofs leak the credential, and the answer is in `prover.py`.

### Where the randomness comes from

A correct implementation samples a fresh blinding vector per transcript. This one
samples a single latent state of two lanes, once, and derives every transcript's
blind from it:

```python
state  = tuple(sample_scalars(parsed.dimension, parsed.q) for _ in range(2))
offset = _apply_route(state, route, parsed.q)
#        = [ route[0]*state[0][j] + route[1]*state[1][j]  for j ]  mod q
```

Substitute that into the response equation and every transcript is linear in the
unknowns `s0`, `s1` and the credential `V`:

```
z[i][j] = route[i][0]*s0[j] + route[i][1]*s1[j] + c[i]*V[j]   (mod q)
```

Three transcripts, eight components, and per component that is three unknowns
with three equations:

```
[ route[0][0]  route[0][1]  c[0] ] [ s0[j] ]   [ z[0][j] ]
[ route[1][0]  route[1][1]  c[1] ] [ s1[j] ] = [ z[1][j] ]
[ route[2][0]  route[2][1]  c[2] ] [ V[j]  ]   [ z[2][j] ]
```

Everything in the matrix is public: the routes are in the bundle (`[23,71]`,
`[131,19]`, `[211,173]`) and the challenges are recomputable. Those routes span,
so each 3x3 system inverts and `V` comes out in closed form with Gaussian
elimination over GF(q). No discrete log, no forgery, no brute force. Two lanes of
randomness cannot hide an eight-component secret from three transcripts: 24
equations, 24 unknowns.

### Getting and testing the flag

The files the box served are here: [proof_bundle.json](/blog/files/blubank-ctf-writeups/softfocus/proof_bundle.json)
(3.9 KB), [prover.py](/blog/files/blubank-ctf-writeups/softfocus/prover.py)
(2.6 KB) and [verifier.py](/blog/files/blubank-ctf-writeups/softfocus/verifier.py)
(12 KB), alongside [softfocus_solve.py](/blog/files/blubank-ctf-writeups/softfocus/softfocus_solve.py)
(4.8 KB) and [reproduce_flaw.py](/blog/files/blubank-ctf-writeups/softfocus/reproduce_flaw.py)
(2.3 KB). The second instance's bundle is
[here](/blog/files/blubank-ctf-writeups/softfocus-n3/proof_bundle.json); its
`prover.py` and `verifier.py` are byte-identical to the first instance, which is
why the attack carried over unchanged.

1. Take the bundle, the prover and the verifier.
2. Run the target's own verifier on the bundle. It passes, so the proof is sound
   and the leak has to be somewhere else.
3. Read `prover.py` and find where the blinds come from.
4. Recompute the three challenges, build the 3x3 system per component, solve for
   the credential.
5. Recompute the commitment from the recovered credential and compare.
6. Unmask the attachment with the keystream.

```bash
python3 verifier.py proof_bundle.json    # OK: proof bundle verifies
python3 softfocus_solve.py proof_bundle.json
# BDD{7ace6e3cf983d3b205de1dc3f2dd59af53f133981d8f5fe10b30df54dad1d4a1}

# the flaw is structural, not one lucky bundle
python3 reproduce_flaw.py proof_bundle.json
# [PASS] attack recovers a freshly generated credential from the target's own prover
```

Two checks made this a finding rather than a guess. First, the recovered
credential reproduces the target's own published commitment, which the target
computed before the bundle was ever public:

```
recomputed = 5e3f4795d59b81513a2d99a6f6061490e4ae3e3201f1fbeae25080bf83d961e5
published  = 5e3f4795d59b81513a2d99a6f6061490e4ae3e3201f1fbeae25080bf83d961e5
```

Second, a separate verifier re-implements the challenge derivation, the
commitment, the linear solve and the keystream from scratch, without importing the
target's `verifier.py`, so a shared bug cannot make a wrong answer look right.

The check I like most is the third one. `reproduce_flaw.py` runs the **target's
own prover** on a credential I chose at random, then attacks the freshly generated
proof:

```
[*] credential chosen by us  : 30c604da5c3fd3e10db1184b6be0461c782d1b3204034757e78fdfd36146f505 ...
[*] credential recovered     : 30c604da5c3fd3e10db1184b6be0461c782d1b3204034757e78fdfd36146f505 ...
[PASS] attack recovers a freshly generated credential from the target's own prover
```

That moves the claim from "I broke this one bundle" to "the randomness derivation
is broken", which is the difference between a solve and an understanding.

The fix is one line of intent: sample an independent blinding vector inside the
transcript loop instead of projecting one two-lane state through the routes. With
independent blinds, the response equations no longer share unknowns and the system
has more unknowns than equations.

### The dead end worth recording

The obvious attack is to look for a linear dependence among the challenges:
find `mu = (1, l1, l2)` such that `l1*route[1] + l2*route[2] = route[0]` and
`sum mu_i*c_i = 0 mod q`. That would let me eliminate the blinds without touching
the state. It does not work, and the reason is worth understanding: the challenge
hash commits to `commitment`, which depends on `(s0, s1, V)`, while the route
relation constrains only `(s0, s1)`. Verified numerically: the sum comes out to
`1869…7704 mod q`, not zero. That failure is what pointed me at solving for the
state instead.

## The same challenge, served again

The platform handed out a second instance of `SoftFocus` on a different host.
`prover.py` and `verifier.py` were byte-identical to the first instance; only the
bundle differed, with a fresh credential and blinding state. The flaw was
unchanged, so the attack was the same, and it took four requests again.

What made the repeat cheap was generalising the PoCs instead of copying them. The
solver now takes a bundle path as an argument, and the verifier checks the
`BDD{64 hex}` format rather than comparing against a hardcoded flag literal. That
literal was a transcription slip waiting to happen on the first instance, and
removing it meant the second instance needed no edits at all.

The new flag differed from the first, which is the useful part: the same unpatched
defect produced a different secret, so this was not a cached answer from the
earlier run.

## Tools

| Tool | Used for |
|---|---|
| `objdump -d -M intel`, `readelf`, `strings` | Matcha disassembly and triage |
| `jadx` | GreenChain dex decompilation |
| `aapt dump badging/permissions` | Reading the Android manifest without a device |
| `unzip`, `xxd`, `dd` | Pulling dex files and assets, splitting IV from ciphertext |
| `openssl enc -d -aes-128-cbc` | Independent AES decryption for verification |
| `sympy` | Factoring the 63-bit modulus once, interactively |
| `python3` + `cryptography` 45.0.7 | secp256k1 point derivation and ECDSA verification |
| `curl` | Four requests per SoftFocus instance, serial, one second apart |

No scanners, no fuzzers, no wordlists on the web challenges. The two local
challenges sent nothing anywhere.

## What I took away

- **Known plaintext beats a confident disassembly.** On Matcha, my model was wrong
  once, and running the real binary against a chosen input caught it in seconds.
  Any claim about what a binary does is testable against the binary.
- **Verify with a different tool than the one that found it.** The GreenChain flag
  came out of my solver and was confirmed by `openssl` on the command line. The
  SoftFocus credential came out of Gaussian elimination and was confirmed by
  recomputing the commitment the target published. Sharing code between the solve
  and the check means sharing bugs.
- **Proofs are only as private as their randomness.** The SoftFocus verifier is
  correct and the bundle passes it. The zero-knowledge property still fails,
  because the blinds came from a two-lane state and there were three transcripts.
  Soundness and privacy fail in different places, and a passing verifier only
  tests one of them.
- **A trust anchor you ship is not a trust anchor.** GreenChain's signature gate
  is real cryptography wrapped around a key that travels with the app, encrypted
  under something every user already has.
- **Write the dead ends down.** The failed linear-dependence attack on SoftFocus,
  the wrong Matcha model, the `jadx` path rules, the RSA `S` versus `S + D`
  ambiguity: each one cost me time once and would have cost it again.
