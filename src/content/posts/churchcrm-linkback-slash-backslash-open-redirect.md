---
title: "A slash and a backslash: open redirect in ChurchCRM's linkBack"
description: "ChurchCRM's redirect guard rejected // and it rejected a leading backslash. It never considered the two characters together, and to a browser they are the same character."
date: 2026-11-01
tags:
  - Vulnerability Research
  - Web Security
draft: false
---

The request was `GET /PledgeDetails.php?PledgeID=999999&linkBack=/%5Cevil.com`,
sent with a normal signed-in session. The response was a 302 with this header:

```text
Location: /\\evil.com
```

A browser reads that as `//evil.com` and leaves for `http://evil.com/`. The value
had just passed `RedirectUtils::validateRedirectUrl()`, the helper ChurchCRM uses
to keep `linkBack` on the site.

That helper is not naive. On 7.7.1 it rejects control characters, protocol
schemes, protocol-relative URLs and backslash-prefixed URLs. For the last two
cases it has one regex each, one per spelling, and the gap between them is two
characters wide.

> [!NOTE] TL;DR
> `validateRedirectUrl()` blocks `//` with one anchored regex and a leading `\`
> with a second. A value beginning `/\` matches neither, because each check is
> pinned to the first character and each knows only one spelling of the
> separator. Browsers treat `\` as `/` in an http(s) URL, so `/\evil.com` resolves
> to `http://evil.com/`. Fixed in 7.8.1 by replacing the two checks with one that
> matches any pair of separators, in either spelling.

## The guard

Here are the two checks as they exist in 7.7.1, in
`src/ChurchCRM/Utils/RedirectUtils.php`:

```php
// Check for protocol-relative URLs (//example.com)
if (preg_match('#^//#', $decodedUrl)) {
    LoggerUtils::getAppLogger()->warning('Rejected protocol-relative redirect URL', ['url' => $url]);

    return $fallback;
}

// Check for backslash-based URLs that could be interpreted as protocol-relative
// Some browsers interpret \\ the same as //
if (preg_match('#^\\\\#', $decodedUrl)) {
    LoggerUtils::getAppLogger()->warning('Rejected backslash redirect URL', ['url' => $url]);

    return $fallback;
}
```

The first pattern matches a value that starts with two forward slashes. The
second matches a value whose first character is a backslash. Both are anchored
with `^`, so both are asking a question about position zero and nothing else.

Deciding whether a URL leaves the origin is not a question about the first
character. It is a question about the authority. When a browser parses
`/\evil.com` against an http or https base, it treats `/` and `\` as the same
separator, sees two of them, and reads what follows as a host. The value never
has to resemble `//evil.com`. It only has to start with two characters that the
parser considers slashes, and it has four ways to do that.

So the two checks each enumerate one spelling of a two-character separator run.
`//` is covered. A leading `\` is covered. `/\` and `\/` are not, and the first of
those is enough.

There is a detail in the response header that took me a moment. It contains two
backslashes, not one. `getLinkBackFromRequest()` passes the value through
`InputUtils::legacyFilterInput()`, which calls `mysqli_real_escape_string()`, and
that escapes a backslash into a doubled backslash. So the validator is handed
`/\\evil.com`, whose first character is still a forward slash, and the check
still misses. The doubling does not rescue anything either, because a browser
collapses any run of separators. `/\\evil.com` still starts an authority.

## Confirming it in the application

`PledgeDetails.php` looks the pledge up at line 29 and redirects at line 30 when
the lookup returns null. A PledgeID that does not exist takes that branch, so the
redirect fires before any pledge data is loaded and before the page renders. The
same file checks for Finance permission at line 22, so the session in the proof
below belongs to a user with Finance enabled.

```text
GET /PledgeDetails.php?PledgeID=999999&linkBack=/%5Cevil.com
Cookie: <authenticated session>

HTTP/1.1 302 Found
Location: /\\evil.com
```

Two negative controls on the same session, because a redirect that fires on
everything would prove nothing:

```text
linkBack=%2F%2Fevil.com   ->  Location: /v2/dashboard     (rejected, fallback)
no session at all         ->  Location: /session/begin
```

The second control matters for a different reason: without a session the request
dies at authentication and never reaches the sink, which is why the proof needs
an account at all.

I also ran the validator on its own, outside the app, to make sure the behaviour
was the regex and not something in the request path:

```text
'//evil.com'      REJECTED
'\evil.com'       REJECTED      leading backslash, caught
'/\evil.com'      PASSES        the bypass
'/v2/dashboard'   PASSES
```

The payload goes out as `%5C`, a plain percent-escape, with no double encoding
and no Unicode trickery. `urldecode` inside the validator turns it into a real
backslash before the checks run, so the guard is not being fooled by an encoding
mismatch. It is being fooled by the shape of the value.

There is a second sink. `WhyCameEditor.php` reads the same `linkBack` at line 20
and redirects to it at line 56 after a POST, and that page is reachable by more
users than the Finance one. I used `PledgeDetails.php` for the proof because it
reaches `RedirectUtils::redirect()` with no valid PledgeID at all, which keeps the
request down to two parameters.

## What the previous fix left behind

This parameter has a history. Two earlier advisories, GHSA-v3hj-33xf-qx47 and
GHSA-5g52-rvjf-6wwf, covered the `//` form of the same open redirect, and both
were closed by PR #7993, "Fix open redirect vulnerability via linkBack URL
parameter", merged in February 2026. That pull request is where these two checks
came from. I confirmed it against the repository: the commit touches
`RedirectUtils.php`, and the two patterns above are what it added.

So the guard was written in response to a real report about `//`, and it handled
`//`, and it handled the backslash form too, as long as the backslash came first.
The version I tested was byte-identical on master when I reported it, which is the
uncomfortable part. A guard that enumerates spellings only ever covers the ones
someone has already been bitten by.

## The fix

The fix shipped in 7.8.1, and it is the one I suggested. The two checks collapse
into a single test on the separator run:

```php
// 7.7.1
if (preg_match('#^//#', $decodedUrl)) {

// 7.8.1
if (preg_match('#^[/\\\\]{2}#', $decodedUrl)) {
```

In the second form the pattern is a character class of forward slash and
backslash, repeated twice, still anchored at the start. That matches `//`, `/\`,
`\/` and `\\`, which are all of the ways a value can begin with a separator run.
The older check further down the function is now redundant, since anything it
catches has already been caught, but it is harmless.

I verified the change by diffing the file across tags: 7.7.1 carries the old
pattern, and 7.8.1, 7.8.2 and current master all carry the new one with identical
bytes.

The stronger version of the same idea is not to pattern-match at all. Parse the
candidate against `SystemURLs::getURL()` and require the origin to match before
redirecting. That removes the whole family of problems at once, at the cost of
more code. The regex is enough here because the value is always expected to be
root-relative.

Whichever form it takes, the fix belongs in this one helper. The same function
serves `stripAndValidatePath()`, which validates the post-login return URL, so
every redirect target in the app inherits the correction.

## Disclosure

I reported this to ChurchCRM through a private security advisory on 2 October.
The maintainer triaged it against master on 2026-10-10, confirmed the bypass, and
shipped a fix eight days later. No CVE was assigned, and the maintainer credited
me as the reporter.

Low is the right score and I would not argue for more. An authenticated user who
follows a crafted link on the ChurchCRM host lands on an external origin. The
link they clicked is on your domain, and it can drop them on a page that imitates
the ChurchCRM login form, which is a phishing primitive and nothing more. There
is no server-side data exposure here and no state change. The redirect does not
know or care who is signed in.

| Field    | Value |
|----------|-------|
| Advisory | [GHSA-jmfg-pc4m-xp53](https://github.com/ChurchCRM/CRM/security/advisories/GHSA-jmfg-pc4m-xp53) |
| CVE      | Not assigned |
| Severity | Low, CVSS 3.5 (`CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:U/C:N/I:L/A:N`) |
| Weakness | [CWE-601](https://cwe.mitre.org/data/definitions/601.html) |
| Affected | 7.7.1 and earlier |
| Patched  | [7.8.1](https://github.com/ChurchCRM/CRM/releases/tag/7.8.1) |

## What I took away

The pattern I keep meeting is a validator that was written by fixing a bug rather
than by naming a property. The property here is "the value must not start an
authority". The code that got written was "the value must not start with `//`
and must not start with `\`", which is the property for two of the four inputs
that satisfy it.

The tell is the anchor. A `^` in a URL check is usually a sign that someone is
looking at the first character when they should be looking at a token. Separators
are a run, not a character, and any check that matches one spelling of a run is
going to have a second spelling waiting behind it.

What makes this one worth writing up is the prior fix. The `//` case was already
known, reported, and patched. The gap that survived the patch is not exotic: it
is the mixed form of two characters the same commit was already thinking about.
A guard can be correct for every input its author had in mind and still wrong,
and the way to tell is not to test the spellings you thought of, but to ask what
the parser downstream is actually going to do with the value.
