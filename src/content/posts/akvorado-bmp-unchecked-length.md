---
title: "A 6-byte packet exhausts memory in Akvorado's BMP server"
description: "Akvorado's BMP server sizes its body buffer by subtracting the header size from the length field, in unsigned 32-bit arithmetic. Anything under 6 bytes wraps to about 4 GiB, and eight connections killed the process. CVSS 7.5, GHSA-wr88-h9r3-fqh3."
date: 2026-10-04
tags:
  - Vulnerability Research
---

We run [Akvorado](https://github.com/akvorado/akvorado) at work. It is a flow
collector and visualizer: it takes NetFlow, IPFIX and sFlow from our routers and
turns them into per-user traffic numbers we use for billing. I open it most days
to answer a question. I did not expect to end up reporting a vulnerability in it.

What I do expect, whenever I have the time, is to poke at the tools I use: read how
they parse input, click the paths that are not meant for me, wonder what happens
with something the tool is not expecting. Akvorado learns routing context over
[BMP](https://datatracker.ietf.org/doc/html/rfc7854), the BGP Monitoring Protocol,
which means it runs a server that routers connect to and stream raw binary messages
into. BMP messages are length-prefixed. A length-prefixed parser is the kind of
code I cannot leave alone, so one afternoon I stopped using the tool and started
reading how it reads.

The payoff was larger than I expected. One 6-byte packet makes the server reserve
about 4 GiB of memory, and a handful of connections is enough to crash the process.
No login, no handshake, and the listener is on by default. Finding something like
that in software you rely on is a mixed feeling. The maintainers confirmed it, fixed
it and credited me, so it is public now and I can write it up.

> [!NOTE] TL;DR
> The BMP read loop takes the 4-byte `Length` field from each message and computes
> `Length - 6` to size the body buffer, in unsigned 32-bit arithmetic. Any `Length`
> below 6 underflows to roughly 4.29 billion, so one tiny packet asks for about
> 4 GiB. `io.ReadFull` then blocks waiting for a body that never arrives, and the
> allocation stays pinned to the connection. Eight connections reached 34 GiB and
> the process died. The fix is to reject any length smaller than the header before
> allocating.

## One minute on BMP

Most of what I understand about BMP, I owe to our network manager, who walked me
through it more than once while I kept asking why it behaves the way it does.

The only part that matters here is the common header, defined in
[RFC 7854](https://datatracker.ietf.org/doc/html/rfc7854). Every BMP message starts
with 6 bytes:

- **Version** (1 byte)
- **Message Length** (4 bytes), the total length of the message including the header
- **Message Type** (1 byte)

A receiver reads those 6 bytes, learns how long the whole message should be, and
reads the rest. The length field is attacker-controlled by definition. It is
whatever the peer on the other end of the TCP connection says it is.

## The line that caught my eye

I was skimming the read loop in `outlet/routing/provider/bmp/serve.go` when this
stopped me:

```go
body := make([]byte, msg.Header.Length-bmp.BMP_HEADER_SIZE)
_, err = io.ReadFull(conn, body) // blocks until `body` is filled
```

A buffer sized straight from a number that came off the wire is the first thing I
look for in a parser of this shape, and it raises the same two questions every
time. What are the bounds of that value, and does anything check them before the
code trusts it? I read the surrounding code twice looking for a guard. There is
none, and the arithmetic below makes the worst case worse than a plain large
allocation.

## Subtraction that wraps

`BMP_HEADER_SIZE` is 6 and `msg.Header.Length` is a `uint32`. Subtracting one from
the other gives the body size, which is correct as long as `Length` is at least 6.
Unsigned subtraction does not go negative. It wraps:

| `Length` sent | `Length - 6` | Allocation                   |
|--------------:|--------------|------------------------------|
| 0             | wraps        | 4,294,967,290 bytes (~4 GiB) |
| 1             | wraps        | 4,294,967,291 bytes (~4 GiB) |
| 5             | wraps        | 4,294,967,295 bytes (~4 GiB) |

A `Length` of 0 asks for about 4 GiB, not 0 bytes. What turns that into a dependable
problem rather than a transient one is the next line: because the attacker never
sends a body, `io.ReadFull` blocks forever waiting for bytes that will not come.
The buffer is never freed. It stays reserved for the lifetime of the connection, and
the attacker controls that lifetime by doing nothing, simply by not closing the
socket.

## Six bytes that prove it

I did not want to argue from theory, so I wrote the smallest thing that could
demonstrate it. The length header is the first thing the server parses, so the whole
exploit fits in six bytes and there is no handshake to get past:

```text
03 00 00 00 00 04
```

Against the common header:

- `03`: BMP version 3, which passes the version check
- `00 00 00 00`: Length = 0, the underflow trigger
- `04`: message type (initiation), a value the server accepts

Sending it:

```python
import socket
s = socket.create_connection(("outlet-host", 10179))
s.sendall(bytes.fromhex("030000000004"))
```

That pins roughly 4 GiB and holds the socket open. One socket proves the allocation.
The crash needs a handful, and since the trick is to do nothing after sending,
"scaling" is just keeping the sockets referenced so Python does not garbage-collect
them out from under you:

```python
import socket, time

PACKET = bytes.fromhex("030000000004")
conns = []
for _ in range(4):
    s = socket.create_connection(("outlet-host", 10179))
    s.sendall(PACKET)
    conns.append(s)  # keep a reference so the socket stays open

time.sleep(3600)  # sit here doing nothing; the ~4 GiB per connection stays pinned
```

Four connections is about 16 GiB reserved from four 6-byte packets. Point it at a box
with less headroom, or raise the range, and you are at the out-of-memory line.

## Watching it fall over

What makes this a 7.5 rather than a footnote is the context around that one line. The
BMP listener is enabled by default and binds port `10179` on all interfaces, so on a
default deployment there is no configuration step and no credential between an
attacker and the bug. In CVSS terms it is `A:H` with `C:N/I:N`: it takes the service
down without touching data.

I stood up my own instance and watched it happen, because watching a number climb is
more convincing than reasoning about it. With `htop` open next to the terminal I was
firing packets from, I opened connections one at a time and watched the `VIRT` column
for the Akvorado process. Eight was enough. Virtual memory reached 34.03 GiB and the
process died with:

```text
runtime: out of memory: cannot allocate 4294967296-byte block
```

Scaling the attack is not clever. It is opening more sockets. That is the part that
sat with me while I remembered this is the tool we point at our own traffic every
day.

## The fix

The fix is the check that should have been there from the start: reject any length
smaller than the header before using it to size anything.

```go
if msg.Header.Length < bmp.BMP_HEADER_SIZE {
    logger.Warn().Uint32("length", msg.Header.Length).
        Msg("invalid BMP message length")
    return nil
}
body := make([]byte, msg.Header.Length-bmp.BMP_HEADER_SIZE)
```

A sane upper bound on message size is worth adding at the same time, so that a large
but technically valid length cannot be used for a big allocation either. The patch
landed in [2026.10.0](https://github.com/akvorado/akvorado/releases/tag/v2026.10.0).
If you expose BMP or IPFIX on an untrusted network, upgrade before you finish reading
this.

## Disclosure

I reported this to the Akvorado maintainers, who confirmed it quickly and shipped the
fix. I am credited in both the
[advisory](https://github.com/akvorado/akvorado/security/advisories/GHSA-wr88-h9r3-fqh3)
and the [2026.10.0 release notes](https://github.com/akvorado/akvorado/releases/tag/v2026.10.0).

| Field      | Value                                                                 |
|------------|-----------------------------------------------------------------------|
| Advisory   | [GHSA-wr88-h9r3-fqh3](https://github.com/akvorado/akvorado/security/advisories/GHSA-wr88-h9r3-fqh3) |
| Severity   | High, CVSS 7.5 (`CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H`)        |
| Weaknesses | [CWE-20](https://cwe.mitre.org/data/definitions/20.html), [CWE-191](https://cwe.mitre.org/data/definitions/191.html), [CWE-400](https://cwe.mitre.org/data/definitions/400.html) |
| Affected   | 2.0.0-beta.1 through 2026.8.1                                          |
| Patched    | [2026.10.0](https://github.com/akvorado/akvorado/releases/tag/v2026.10.0) |

## What I took away

- **Length fields that feed allocations are where I probe first.** Before anything
  clever, I test the boundaries of a size value that came off the wire: zero, values
  below the header size, and values near the integer maximum. This bug lived at the
  smallest input, not the largest.
- **Unsigned subtraction is a trapdoor.** `a - b` with `a < b` does not error in
  `uint32`, it wraps to something enormous. Any subtraction on attacker-influenced
  unsigned values needs a bounds check first, every time.
- **An allocation is only half of the primitive.** What made this a reliable crash was
  that `io.ReadFull` blocked and kept the memory pinned. The damaging resource bugs are
  the ones where the attacker controls the size and how long it stays reserved.
- **A default-on listener changes the severity.** The same flaw behind an
  off-by-default feature would be a much smaller issue. This one shipped enabled on all
  interfaces, and that is most of the distance between "bug" and "unauthenticated
  remote crash."

What stayed with me is how ordinary the setup was. I was not fuzzing anything exotic.
I was reading a tool I already trusted, following a habit, and the bug was sitting in
plain sight.
