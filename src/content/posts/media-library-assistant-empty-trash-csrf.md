---
title: "One request empties the trash in Media Library Assistant 3.41"
description: "A missing nonce lets a page an Editor visits force-delete every trashed attachment in Media Library Assistant. CVE-2026-113486, fixed in 3.42."
date: 2026-11-11
tags:
  - Vulnerability Research
  - Web Security
draft: false
---

Media Library Assistant lets an Editor or Administrator empty the plugin's
attachment trash with one GET request. The handler that does the deleting has no
nonce check of its own, and WordPress core's nonce check does not run early
enough to stop it. So a page the victim merely visits can wipe every trashed
attachment on the site, permanently: the files leave the disk, not just the
media library view.

WPScan published the advisory for **CVE-2026-113486** on 2026-10-26, and the
plugin shipped the fix in 3.42. This post goes up now that the advisory is
public.

> [!NOTE] TL;DR
> In `media-library-assistant` 3.41, `MLA::mla_render_admin_page()` handles
> `$_REQUEST['delete_all']` with no `check_admin_referer()` anywhere in the
> branch. Core's `upload.php` does call `check_admin_referer( 'bulk-media' )`,
> but MLA processes its page on the `load-upload.php` hook, which fires before
> that line in `upload.php` ever executes. The deletion has already happened by
> the time core refuses the request. Fix: 3.42 adds `check_admin_referer(
> 'bulk-attachments' )`, the nonce the bulk form already carries, to that branch.

## The action involved

Media Library Assistant adds a Media → Assistant screen on top of WordPress's
own media list. Among the bulk actions is **Empty Trash**. It is the ordinary,
destructive, "yes, really" action of that screen: it walks every attachment with
`post_status = 'trash'` and deletes each one.

The bulk of the work happens in `includes/class-mla-main.php`, inside
`MLA::mla_render_admin_page()`:

```php
// Empty the Trash?
if ( isset( $_REQUEST['delete_all'] ) ) {
    global $wpdb;
    $ids = $wpdb->get_col( $wpdb->prepare( "SELECT ID FROM $wpdb->posts WHERE post_type=%s AND post_status = %s", 'attachment', 'trash' ) );
    $delete_count = 0;
    foreach ( $ids as $post_id ) {
        $item_content = self::_delete_single_item( $post_id );
        // ...
```

The request parameter is read straight out of `$_REQUEST`, the rows are
selected, and each one goes to `_delete_single_item()`. There is no
`check_admin_referer()`, no `check_ajax_referer()`, and no nonce value of any
kind in the block.

That is worth being precise about, because MLA does use nonces elsewhere in
the same file: `check_admin_referer( 'bulk-attachments' )` sits at line 200,
inside `MLA::mla_admin_init_action()`, and covers the `download-zip` and
`download-original` bulk actions. It is a different function handling different
verbs. The Empty Trash branch never reaches it.

## Why core's nonce does not save you

My first instinct was that this had to be a false positive. WordPress core
protects its own bulk media actions: `wp-admin/upload.php` calls
`check_admin_referer( 'bulk-media' )` before dispatching anything, and
`WP_Media_List_Table::current_action()` returns `delete_all` before it consults
the parent `filter_action` branch. Both of those point at a request that should
be rejected.

It is not rejected, and the reason is the hook ordering. MLA handles the media
screen on the `load-upload.php` hook, registered in `includes/class-mla-main.php`
(line 506 in 3.41):

```php
add_action( 'load-upload.php', 'MLA::mla_load_media_action' );
```

`load-{page}.php` fires while WordPress is still setting up the admin page,
before `upload.php`'s body runs. So on a request like
`upload.php?page=mla-menu&delete_all=1`, MLA's handler executes first and the
trash is empty before core's nonce check gets its turn. Core then prints
"Sorry, you are not allowed", which is technically true and entirely too late.

Any unguarded request handler on that hook is reachable without a nonce,
regardless of what `upload.php` checks afterwards. That ordering is the actual
lesson of this finding.

## The test that settled it

Reasoning about hook order was not enough, so I ran the same parameter against
core's path and against the plugin's page on a local instance, as an
Administrator, with no nonce:

| Request | Outcome |
|---|---|
| `GET /wp-admin/upload.php?delete_all=1` | refused, nonce error |
| `GET /wp-admin/upload.php?page=mla-menu&delete_all=1` | all trashed attachments deleted |

The two requests differ by one parameter, `page=mla-menu`. That isolated the
plugin's `load-` hook as the thing running ahead of the guard. The full probe
run, with counts read before and after each request:

```text
E1  core path,   no nonce      GET /wp-admin/upload.php?delete_all=1
      -> HTTP 200, "Sorry, you are not allowed", trashed 9 -> 9        REFUSED
E2  plugin path, no nonce      GET /wp-admin/upload.php?page=mla-menu&delete_all=1
      -> HTTP 200, "12 items deleted",          trashed 12 -> 0       DELETED
E3  core path,   bogus nonce   ...?delete_all=1&_wpnonce=deadbeef00
      -> HTTP 200, "Sorry, you are not allowed", trashed 3 -> 3        REFUSED
E4  plugin path, bogus nonce   ...?page=mla-menu&delete_all=1&_wpnonce=deadbeef00
      -> HTTP 200, "6 items deleted",           trashed 6 -> 0        DELETED
```

E3 and E4 are the pair I care about. Supplying a wrong nonce does not change the
outcome on the plugin path, which is what a branch that never consults a nonce
looks like in practice.

Then the same request once per role:

```text
administrator  page=200  trashed 5->0  "items deleted"     DELETED EVERYTHING
editor         page=200  trashed 3->0  "items deleted"     DELETED EVERYTHING
author         page=200  trashed 3->3  "No items deleted"  not deleted
subscriber     page=302  authentication refused
```

Editor is the minimum role, and Editor is common on sites that have more than
one person publishing. Authors are refused by the plugin's own capability
check, so this is not a case where every logged-in user is a viable target.

## Deletion here means deletion

The rows are not moved to the Trash, they are removed from it.
`_delete_single_item()` calls `wp_delete_attachment( $post_id, true )`
(`class-mla-main.php:2704`), and the `true` is the force-delete argument. The
files are unlinked from disk and the database rows are gone. There is nothing
in the WordPress admin to restore afterwards.

The attacker chooses the timing, not the contents. That is the part that makes
it practically annoying rather than theoretically annoying: the request only
helps if the Trash currently holds something someone wanted to keep, and media
trash is exactly where people park things while deciding. In a normal workflow
that window is measured in days, sometimes weeks.

## On multisite

Findings of this class tend to be assessed against multisite, and arguing from
"the plugin contains no multisite code" is not evidence, so I built a real
two-site subdomain network with MLA network-activated and measured it.

| Test | Request | Result |
|---|---|---|
| M1 | site 1: `http://lab.test/wp-admin/upload.php?page=mla-menu&delete_all=1` | site 1 trash 16 → 0, site 2 17 → 17 untouched |
| M2 | site 2: same path on `news.lab.test` | site 2 trash 21 → 0 |
| M3 | site 1, session is Subscriber on site 1, Administrator on site 2 | HTTP 403, trash 3 → 3, refused |
| M4 | seed both sites, send one request to site 1 | site 1 8 → 0, site 2 5 → 5 untouched |

The CSRF works on a network. What it does not do is cross sites: M4 seeds both
trashes, sends a single request, and only the targeted site's trash empties.
The handler reads `$wpdb->posts`, the current blog's table, takes no `blog_id`,
and never calls `switch_to_blog()`. MLA registers no network admin page either.
M3 shows the role check is per site, as it should be: a user who is Subscriber
on site 1 does not get to empty site 1's trash because they are an Administrator
on site 2.

So on a network the impact is the same as on a single site, scoped to whichever
site the victim holds a session on. I did not find a network-wide effect and I
am not claiming one.

## A missed sibling of an earlier fix

This is not a new class of bug in MLA, and it would be misleading to present it
as one. The vendor already fixed CSRF of this shape once:

- WPScan advisory: "Media Library Assistant < 3.36, Cross-Site Request Forgery
  via Bulk Action Form", fixed in 3.36, rated 8.1 high, dated 2026-05-28.
- The 3.36 changelog names it **CVE-2026-6075**, described as a CSRF risk for
  the Settings / Media Library Assistant tabs.

That fix added `check_admin_referer( MLACore::MLA_ADMIN_NONCE_ACTION, MLACore::MLA_ADMIN_NONCE_NAME )`
to the settings tab handlers:

```text
class-mla-settings-view-tab.php        +1 nonce check
class-mla-settings-upload-tab.php      +1 nonce check
class-mla-settings-shortcodes-tab.php  +1 nonce check
```

`class-mla-main.php` was not touched. It is byte-identical between 3.35 and
3.36, zero changed lines, and the `delete_all` block above is still there in
3.41, the last release before the fix. The vulnerable code is present in 3.35,
3.36 and 3.41, and 3.42 adds the missing check to that branch.

The reason I still reported it, rather than filing it as a duplicate, is the
outcome: the surface that got patched changed settings, and this one destroys
media files with no recovery path.

## Impact and what I am not claiming

Demonstrated: an Editor or Administrator session can be made to permanently
force-delete every trashed attachment on the site, with no nonce and no
interaction beyond loading a page. Reproduced on a single-site install and on a
multisite network, where the effect stays inside the targeted site.

Not claimed: no account takeover, no data disclosure, no code execution, and no
cross-site or network-wide deletion. Attachments that are not already in the
Trash are unaffected by this request; I did not demonstrate deletion of
published files.

WPScan rates it 6.5 Medium, `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N`,
scoring the victim's page load as user interaction. My submission used 6.4 with
`PR:L` and `UI:N`; either way the practical requirement is the same, a victim
logged in as Editor or above, which is why this is not a 9 and not an
unauthenticated bug.

## The fix

3.42 fixes it the way I suggested, with one improvement: it reuses the nonce
the bulk form already carries instead of introducing another one.

```php
if ( isset( $_REQUEST['delete_all'] ) ) {
    global $wpdb;

    check_admin_referer( 'bulk-attachments' ); // set in class-mla-list-table.php function display_tablenav()
```

That nonce comes from `wp_nonce_field( 'bulk-attachments' )` in
`MLA_List_Table::display_tablenav()` (`class-mla-list-table.php:2083`), so the
Empty Trash button needed no UI change and the fix costs one line. The same
review should still cover the other branches of `mla_render_admin_page()` that
act on request data, because the `load-` hook ordering that makes this
reachable applies to all of them equally.

## Disclosure status

I submitted this through WPScan (#51141). They published the advisory on
2026-10-26 and NVD picked up the CVE on 2026-10-28. The vendor shipped the fix
in 3.42.

| Field | Value |
|---|---|
| Advisory | [Media Library Assistant < 3.42 - Trashed Attachment Deletion via CSRF](https://wpscan.com/vulnerability/29f5c90d-564a-4844-bf8e-b72243da5a0a/) |
| CVE | [CVE-2026-113486](https://nvd.nist.gov/vuln/detail/CVE-2026-113486) |
| Severity | Medium, 6.5 (`AV:N/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N`) |
| Weakness | [CWE-352](https://cwe.mitre.org/data/definitions/352.html) |
| Affected | Media Library Assistant 3.35, 3.36 and 3.41 (3.41 tested) |
| Patched | Media Library Assistant [3.42](https://downloads.wordpress.org/plugin/media-library-assistant.3.42.zip) |

## What I took away

- **Hook order is a security boundary.** `load-upload.php` runs before
  `upload.php`'s body, so a plugin that handles a destructive verb on the load
  hook is outside the nonce check the page appears to rely on. When reviewing a
  plugin's admin page, the question is not "does core check a nonce" but "which
  code runs first".
- **A wrong nonce in the request proves nothing if nothing reads it.** E3 and E4
  are the cheap discriminator: send a bogus `_wpnonce` to both paths. If the
  plugin path still deletes, the guard is not wired to that branch.
- **Fixed one endpoint does not mean the class is closed.** The 3.36 patch was
  real and correct for the settings tabs. It did not cover the media screen, and
  the file it skipped is the one that force-deletes files.
- **Measure the multisite claim.** "The plugin has no multisite code" is an
  argument about absence. One request against a seeded two-site network, then
  the same request on the other site, settles the scope in a few minutes and
  keeps the report from overclaiming.
