# Title
Print Preview Sends Embedder's Full URL and Title to Cross-Origin Subframe's Renderer

---

# Description

## Summary

When a cross-origin `<iframe>` triggers `window.print()`, the browser populates the print header/footer with the **top-level embedder's full URL and title** and delivers them into the **subframe's** renderer process for rendering. Only username and password are stripped from the URL — the path and query string (including session tokens, reset tokens, record IDs) survive intact.

This violates Chrome's own documented site-isolation invariant (`docs/security/compromised-renderers.md`) which states that compromised renderers must not be able to read the "Full URL (e.g. URL path or query) of cross-site frames." It also bypasses same-origin policy (`top.location.href` throws SecurityError) and referrer policy (`strict-origin-when-cross-origin` strips the URL to origin-only).

No user gesture is required — `g_is_preview_enabled` is true on desktop, short-circuiting the activation check. An iframe can call `window.print()` from a `load` handler with nothing clicked.

## Steps To Reproduce

1. Start the attached PoC server:
   ```
   python3 poc/server.py
   ```
   This serves origin A on `127.0.0.1:9080` and origin B on `localhost:9081` (different host + port = cross-origin).

1. Open Chromium-based browser (Chrome/Arc/Edge) to:
   ```
   http://127.0.0.1:9080/top.html?session=SUPERSECRET-TOKEN-12345&user=admin
   ```
   This renders a top-level page titled "MyBank - Account Statement" with a sensitive query string, embedding a cross-origin iframe from `localhost:9081`.

1. Observe the iframe correctly shows:
   - `top.location.href` → `BLOCKED (SecurityError)`
   - `document.referrer` → `http://127.0.0.1:9080/` (origin only, path/query stripped)

1. Click the **"window.print()"** button inside the iframe (or open `top-auto.html` for the no-user-gesture variant that auto-prints on load).

1. In the print dialog:
   - Set Destination → **Save as PDF**
   - Expand "More settings" → ensure **Headers and footers** is checked
   - Save the PDF

1. The resulting PDF contains only the **iframe's body content** but the **header and footer are stamped with the embedder's title and full URL**:
   ```
   7/31/26, 4:05 AM                                    ad frame
   Cross-origin iframe (origin B: localhost:9081)
   ...iframe body content...
   127.0.0.1:9080/top.html?session=SUPERSECRET-TOKEN-12345&user=admin     1/1
   ```

1. The full URL including the `session` and `user` query parameters — data denied by every policied cross-origin channel — has been delivered into origin B's renderer process and rendered into the output.

**Additional test cases (all served by the same PoC server):**

| URL | Action | Result |
|-----|--------|--------|
| `/top-notitle.html?session=...` | Click button in iframe | Iframe has empty `<title>` → embedder's title also leaks into header |
| `/top-auto.html?reset_token=SUPERSECRET-TOKEN-12345&email=user@example.com` | **Nothing** — prints on load | Full URL with reset token leaked with zero user interaction |

## Evidence issue doesn't replicate on platform default browsers (Chrome, Safari, Edge)

This is a Chromium-specific bug. It **does** replicate on all Chromium-based browsers:
- **Chrome** (tested on stock 127/128)
- **Arc** (tested — PDF evidence attached)
- **Edge**

It does **not** affect Firefox or Safari, which use different print pipelines.

## Root Cause

In `chrome/browser/ui/webui/print_preview/print_preview_handler.cc`, `HandleGetPreview` resolves the *initiator* (the top-level WebContents) and copies its title and URL into the print settings, sending them to `print_preview_rfh_` (the subframe that called `print()`):

```cpp
if (display_header_footer_opt.value_or(false)) {
    settings.Set(kSettingHeaderFooterTitle, initiator->GetTitle());
    GURL::Replacements url_sanitizer;
    url_sanitizer.ClearUsername();
    url_sanitizer.ClearPassword();
    const GURL& initiator_url = initiator->GetLastCommittedURL();
    settings.Set(kSettingHeaderFooterURL,
                 url_formatter::FormatUrl(
                     initiator_url.ReplaceComponents(url_sanitizer)));
}
```

These settings are then rendered in the subframe's process at `print_render_frame_helper.cc:607-614`:

```cpp
options.Set("url", params.url);
std::u16string title = source_frame.GetDocument().Title().Utf16();
options.Set("title", title.empty() ? params.title : title);
ExecuteScript(&frame, "setupHeaderFooterTemplate(", ...);
```

`CheckForInvalidTargetRenderFrame` only rejects fenced and inactive frames — ordinary cross-origin iframes are accepted as `print_preview_rfh_`.

## Supporting Material/References

- Attached PoC (`poc/`) — self-contained server and HTML files
- Attached PDF evidence (`MyBank - Account Statement.pdf`) — produced in Arc browser showing the leak
- Verification script: `./verify.sh <saved.pdf>` mechanically confirms the embedder's query string reached origin B's output
- Prior art: [crbug 382394786](https://issues.chromium.org/issues/382394786) — same initiator/frame confusion, filed as cosmetic (title shows as wrong filename), does not cover the URL leak or process boundary crossing
- Violates: `docs/security/compromised-renderers.md` — "Compromised renderers shouldn't be able to read the contents of cross-site frames. Examples: ... Full URL (e.g. URL path or query) of cross-site frames."

---

# Impact

1. **Site Isolation / process-boundary violation.** The embedder's full URL (path and query intact) is delivered into a cross-origin renderer process. Top-level URLs routinely carry session identifiers, password-reset tokens, search terms, and record IDs in their query strings. While `setupHeaderFooterTemplate` runs in a Blink-internal frame (preventing trivial script access), the data is placed inside the very process that Chrome's security architecture is designed to keep it out of — a compromised renderer in that process can read it.

2. **Printed-document provenance spoofing.** A malicious third-party iframe (ad network, widget, embedded app) can trigger a print that produces a PDF containing only the iframe's own content, yet branded with the embedding site's URL and title in the header/footer. The saved artifact appears to originate from the embedding site rather than the actual source of the content.

3. **No user interaction required.** The auto-print variant demonstrates that `window.print()` from a `load` handler succeeds without any click, activation, or user gesture — `g_is_preview_enabled` bypasses the throttling gate on desktop.

### Suggested Fix

Use the printing frame's own URL and title for header/footer when `print_preview_rfh_` differs from the initiator's primary main frame. At minimum, apply the same reduction referrer policy already enforces: send only the initiator's origin, not its full URL.
