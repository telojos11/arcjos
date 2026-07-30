# Threat Model — Bug Class Analysis from crbug 503614310

**Pattern**: *Commit-on-Close TOCTOU with Asynchronous Deferral + Synchronous Shortcut*

---

## 1. What the Code Claims to Check

| Claim | Where | Checked? |
|-------|-------|----------|
| The origin shown to the user in the bubble is the origin that receives the permission grant | `ContentSettingBubbleModel` constructor reads `GetPage().GetMainDocument()` at **open time** | ✅ Displayed, but **not preserved** |
| The permission decision is atomic (user's intent at T1 = applied outcome at T2) | Implicit in UI design — user sees "Allow evil.com" and clicks Allow | ❌ **No atomicity guarantee** — nothing re-validates the origin between open and close |
| Navigation during bubble lifetime triggers clean teardown | `ContentSettingBubbleContents::PrimaryPageChanged` → `GetWidget()->Close()` | ⚠️ Closes the widget, but **asynchronously** — widgets teardown is deferred |
| State cannot be overwritten during the close gap | `CommitChanges()` guards with `media_stream_access_origin().is_empty()` | ⚠️ Only protects the **default ASK** state; BLOCK and ALLOW states bypass the guard |

---

## 2. What Happens When Configuration Is Partial or Missing

### The core gap: `CommitChanges()` re-queries the source of truth

The bubble model treats `GetPage().GetMainDocument()` as the authoritative origin **at close time**, not at open time:

```
OPEN TIME (T1):                   CLOSE TIME (T2):
  display origin = victim.com       CommitChanges() reads:
  user selects "Allow"                GetPage().GetMainDocument() → evil.com ← CHANGED
                                   Permission saved to evil.com
```

**The missing configuration**: no cached, immutable origin snapshot at construction time. This is what the fix introduces (matching the prior fix to `ContentSettingStorageAccessBubbleModel`).

### The synchronous shortcut that weaponizes the gap

Normally, the `is_empty()` guard catches this:

```
evil.com navigates → getUserMedia() → prompt shown → origin stays empty → CommitChanges aborts
```

But when evil.com is *already* set to BLOCK:

```
evil.com navigates → getUserMedia() → BLOCK resolves SYNCHRONOUSLY →
  media_stream_access_origin_ = evil.com (populated before CommitChanges runs) →
  CommitChanges reads evil.com → saves ALLOW
```

The BLOCK state skips the user prompt entirely, turning an async gate into a synchronous write — the precise mechanism that bridges the race window.

### Configuration matrix

| Attacker origin state | getUserMedia resolves | `is_empty()` guard | Race exploitable? |
|----------------------|-----------------------|---------------------|-------------------|
| ASK (default) | Async (prompt shown) | ✅ empties origin, CommitChanges aborts | No |
| BLOCK | **Synchronous (immediate deny)** | ❌ origin populated before CommitChanges | **Yes** |
| ALLOW | **Synchronous (immediate grant)** | ❌ origin populated, but user's "Allow" is redundant | No practical gain |

---

## 3. Where Validation Silently Degrades

### Degradation 1: `GetWidget()->Close()` is not a synchronous gate

```
PrimaryPageChanged() → GetWidget()->Close()     // posts a task, returns immediately
renderer executes new document JS               // runs in parallel with...
WindowClosing() → CommitChanges()                // ...still pending widget teardown
```

No event, barrier, or fence prevents the new document from mutating state that the old bubble closure depends on. The close is advisory, not transactional.

### Degradation 2: The `is_empty()` guard looks like a safety check but is a partial one

```cpp
if (content_settings->media_stream_access_origin().is_empty())
    return;  // "no pending request, nothing to do"
```

This checks whether a user-facing prompt is active, **not** whether the origin being written matches the origin the user saw. It's a prompt-liveness check, not an origin-integrity check. In BLOCK/ALLOW states the origin is populated without any prompt, so the guard passes silently.

### Degradation 3: No re-entrancy protection on CommitChanges

Nothing prevents `CommitChanges()` from executing while a permission request initiated by the new page is still in-flight (or has already resolved synchronously). The model has no concept of "this commit belongs to a session that is now stale."

### Degradation 4: `PrimaryPageChanged` closes the widget but doesn't cancel the pending intent

Navigation fires `PrimaryPageChanged`, which closes the UI, but the *semantic intent* of the user's radio-button selection persists in the model. The model remembers "user picked Allow" without remembering "user picked Allow *for origin X at time T1*."

---

## 4. Exploitable Bug Classes Derived from This Pattern

### Class A: Commit-on-Close TOCTOU (all ContentSettingBubbleModel subclasses)

Any bubble that:
1. Displays a target origin to the user at open time
2. Reads the target origin from `GetPage()` at commit time
3. Closes asynchronously on navigation

has the same vulnerability. Candidates:

| Bubble | Dialog | Race surface |
|--------|--------|-------------|
| `ContentSettingMediaStreamBubbleModel` | Camera/mic permission | ✅ Confirmed (503614310) |
| `ContentSettingGeolocationBubbleModel` | Geolocation permission | ⚠️ Same pattern |
| `ContentSettingNotificationsBubbleModel` | Notification permission | ⚠️ Same pattern |
| `ContentSettingMidiSysExBubbleModel` | MIDI permission | ⚠️ Same pattern |
| `ContentSettingClipboardBubbleModel` | Clipboard access | ⚠️ Same pattern |
| `ContentSettingFileSystemBubbleModel` | File system access | ⚠️ Same pattern |
| `ContentSettingStorageAccessBubbleModel` | Storage access | ✅ Already fixed (prior fix cited in report) |

Each needs the same fix: cache the origin in the constructor, use the cached value in `CommitChanges()`.

### Class B: Synchronous Permission Shortcut as Race Enabler

Anywhere a permission controller calls its callback synchronously for pre-determined states (BLOCK, ALLOW) without a user prompt, the synchronous write can interleave with an in-flight async teardown. Hunt for:

```
if (state == BLOCKED) {
    std::move(callback).Run(denied);  // synchronous → overwrites intermediate state
}
if (state == ALLOWED) {
    std::move(callback).Run(granted); // synchronous → overwrites intermediate state
}
```

Candidate locations: `PermissionRequestManager`, `MediaStreamDevicesController`, any `*PermissionContext::DecidePermission`.

### Class C: Widget Teardown as a Race Window

Any Chromium dialog model that uses `views::Widget::Close()` (which posts a task) + reads mutable state in `WindowClosing()` creates the same asynchronous gap. This is not unique to permission bubbles:

- Download shelf / download prompt
- Save-password bubble
- Autofill popup
- Payment handler sheet
- WebAuthn conditional UI

In each case: if closing triggers a side effect that reads "current page state," and navigation can race the close, the same TOCTOU applies.

### Class D: Origin Confusion via `GetPage().GetMainDocument()` at Action Time

Any code path that:
1. Captures user intent at time T1
2. Reads `GetPage().GetMainDocument().GetLastCommittedOrigin()` at time T2
3. Applies a side effect using the T2 origin under the pretense of T1's intent

is exploitable. Grep for `GetPage().GetMainDocument()` in callback/lambda bodies that fire after any async step (task post, IPC response, animation completion).

### Class E: Popup + Navigation Race Chains

The specific exploit chain in 503614310 uses:
```
popup(victim.com) → bubble open → navigate popup to evil.com → synchronous permission → CommitChanges(evil.com)
```

Generalized: any browser UI that inherits its target from the active tab's URL at close time can be confused via a popup that changes what document is "active" between open and close. Popups share a `WebContents` with their opener, so the navigation target and the bubble target diverge.

---

## 5. Remediation Patterns

| Pattern | Fix |
|---------|-----|
| Commit-on-close origin confusion | **Snapshot** the origin at constructor time; use snapshot in `CommitChanges()` |
| Synchronous shortcut interleaving | **Gate** side-effect writes on an `is_closing_` flag or session token |
| Widget teardown race | **Cancel pending intents** in `PrimaryPageChanged` before posting the close task |
| Missing origin-integrity check | **Compare** cached origin to current origin at commit time; abort on mismatch |
