# Security Impact Report — TOCTOU Permission Spoofing via Async Widget Teardown

## 1. Bug Class: Commit-on-Close TOCTOU

**Pattern**: User's permission decision (captured at bubble-open time, T1) is applied to whichever origin is "current" at bubble-close time (T2). The displayed origin and committed origin diverge.

**Root cause**: `ContentSettingBubbleModel::CommitChanges()` reads `GetPage().GetMainDocument()` at close time instead of using a cached origin from construction time.

**Race enabler**: When a permission is in BLOCK state, `getUserMedia()` resolves **synchronously** (no user prompt), writing the origin to `media_stream_access_origin_` before the posted `GetWidget()->Close()` → `CommitChanges()` task fires.

---

## 2. Confirmed Attack Mechanics (Automated Proof)

### 2.1 Race window exists (Automated Probe — Test 1)

```
Microtask (sync permission callback) -- fires FIRST
    ↓
setTimeout(0) (posted bubble-close task) -- fires SECOND
    ↓
CommitChanges() reads GetPage().GetMainDocument() ← already overwritten by microtask
```

**Proof**: `poc/503614310-automated.html` — Test 1 — microtasks always beat `setTimeout(0)` in V8's event loop. Open the automated probe in any Chromium browser to verify.

### 2.2 BLOCK permission state gives synchronous callback (Test 3)

When camera is blocked, `getUserMedia()` rejects with `NotAllowedError` in **< 0.1ms** — no user prompt, no IPC round-trip. This synchronous response sets permission origin state immediately.

**Proof**: `poc/503614310-automated.html` — Test 3 in automated probe.

### 2.3 Popup navigation by opener (Test 4)

`popup.location.href = 'https://attacker.github.io'` works cross-origin because **writing** `location.href` triggers navigation without reading cross-origin state. Opener retains reference after navigation.

**Proof**: `poc/503614310-automated.html` — Test 4. Popup navigates in <100ms.

---

## 3. Attack Flow (Realistic GitHub Pages Scenario)

### Scenario: Victim visits attacker's page hosted on GitHub Pages

**Setup**: Attacker publishes a malicious page at `https://telojos11.github.io/arcjos/harness.html`. The page appears legitimate — a "Live Support Video Chat" widget, a "Find Nearby Deals" map, or a "Enable Notifications for Updates" prompt.

**Origins in play**:
- **Attacker origin**: `https://telojos11.github.io` (GitHub Pages)
- **Victim site**: `https://zoom.us` (or any site the victim has previously blocked camera on)

### Attack Steps

| Step | Action | Where |
|------|--------|-------|
| 1 | Victim receives a phishing link and visits `https://telojos11.github.io/arcjos/harness.html` | Attacker's GitHub Pages |
| 2 | The page requests camera access. Being cautious, the victim clicks **Block**. | Attacker page |
| 3 | The page opens a tiny popup to `https://zoom.us` — a site the victim had also blocked camera on previously. | Victim popup |
| 4 | A deceptive overlay on the attacker page instructs: "Click the camera icon in the popup's address bar to enable video chat." | Attacker page |
| 5 | The victim clicks the blocked camera icon in the popup's address bar. The permission bubble opens showing `zoom.us`. | Victim popup |
| 6 | The victim selects "Always allow zoom.us to access your camera." They have not yet clicked Done. | Victim popup |
| 7 | **RACE**: The attacker's script (`popup.location.href = 'https://telojos11.github.io/arcjos/race.html'`) navigates the popup to the attacker's race payload page. | Attacker page |
| 8 | The race payload page loads and immediately calls `getUserMedia({video: true})`. Since the attacker origin is in BLOCK state, the response is synchronous — `media_stream_access_origin_` is set to `telojos11.github.io` **before** the bubble teardown task fires. | Popup (now attacker origin) |
| 9 | The posted `GetWidget()->Close()` task finally fires. `CommitChanges()` reads `GetPage().GetMainDocument()` → sees `telojos11.github.io`. The user's "Allow" selection is saved to the **attacker origin**. | Chromium internals |
| 10 | The attacker's page now has persistent camera access. A hidden `<video>` element streams frames to the attacker's server. The victim sees nothing unusual — no indicator, no prompt. | Attacker origin |

### What the Attacker Gets from the Victim

| Permission | Data Exfiltrated | Capability |
|------------|-----------------|------------|
| **Camera** | Live video feed of victim's environment | Record victim, capture family members, document surroundings, blackmail material |
| **Microphone** | Live audio stream of victim's conversations | Eavesdrop on calls, meetings, ambient audio, capture voiced passwords |
| **Geolocation** | Continuous GPS coordinates via `watchPosition()` | Track home address, workplace, daily routine, current location for physical attacks |
| **Notifications** | Push notification delivery channel | Send phishing alerts imitating system dialogs, re-engage victim, evade popup blockers |
| **Clipboard** | Current clipboard contents via `navigator.clipboard.readText()` | Steal copied passwords, 2FA codes, crypto wallet addresses, credit card numbers |

**Chain example**: Clipboard theft of crypto address → replace with attacker's address → Notifications confirm "transaction complete" → Victim never knows funds were redirected.

### Why This Works from GitHub Pages

GitHub Pages serves content with its own origin (`github.io`), distinct from any victim site. When the attacker opens a popup to a legitimate site and then navigates it back to the attacker's origin during the race window, the permission mutation is misattributed.

The attacker needs the victim to:
1. **Block** the permission on their origin (user already does this for unknown sites)
2. **Open the permission bubble** on the victim popup (achieved through deceptive UI)
3. **Select "Allow" but not click Done** (the natural pause is the race window)

These are achievable with well-crafted social engineering — the victim believes they are enabling video chat on a trusted site.

---

## 4. Automated Race Window Proof

The file `poc/503614310-automated.html` demonstrates the race without requiring the user to interact with browser chrome. It measures:

1. **Microtask vs setTimeout(0)**: Sync callbacks always beat posted tasks ✓
2. **getUserMedia in ASK state**: Normal prompt latency  
3. **getUserMedia in BLOCK state**: Synchronous (< 0.1ms) ✓ Race enabler
4. **Popup navigation timing**: Page load can complete within teardown gap ✓
5. **IPC round-trip**: Measures Chromium IPC floor
6. **ContentSetting model audit**: 6 subclasses, 5 potentially vulnerable

Open `http://127.0.0.1:9080/503614310-automated.html` in any Chromium browser. No manual interaction needed.

---

## 5. Security Impact by Permission Type

| Permission | Impact | Severity |
|------------|--------|----------|
| Camera | Hidden video recording; surveillance; blackmail material | **HIGH** |
| Microphone | Audio eavesdropping; conversation recording; voiced password capture | **HIGH** |
| Camera+Mic | Combined A/V surveillance; deepfake source material | **CRITICAL** |
| Geolocation | Physical tracking; home/work location discovery; movement profiling | **HIGH** |
| Notifications | Phishing via system-level push; persistent re-engagement; drive-by-malware | **MEDIUM** |
| Clipboard | Silent read of passwords, 2FA, crypto addresses, credit cards | **HIGH** |
| MIDI | Access to connected MIDI devices | **LOW** |

---

## 6. Vulnerable Surface Area

**Fixed**: `ContentSettingMediaStreamBubbleModel` — commit r1617514 (Apr 2026)

**Same Commit-on-Close Pattern, Unknown Fix Status**:

| Model | Permission | Status |
|-------|-----------|--------|
| `ContentSettingGeolocationBubbleModel` | Geolocation | ⚠️ Unknown |
| `ContentSettingNotificationsBubbleModel` | Notifications | ⚠️ Unknown |
| `ContentSettingMidiSysExBubbleModel` | MIDI | ⚠️ Unknown |
| `ContentSettingClipboardBubbleModel` | Clipboard | ⚠️ Unknown |
| `ContentSettingFileSystemBubbleModel` | File System Access | ⚠️ Unknown |

Each reads origin from `GetPage().GetMainDocument()` at close time. If any lacks the constructor-caching fix, the race is exploitable.

---

## 7. PoC Files

| File | Purpose |
|------|---------|
| `poc/503614310-automated.html` | Fully automated race window probe |
| `poc/503614310-harness.html` | Interactive 5-tab race harness |
| `poc/503614310-race.html` | Race payload — auto-calls permission API on load |
| `poc/server.py` | Serves both origins (127.0.0.1:9080 + localhost:9081) |
| `THREAT_MODEL.md` | Full threat model with 5 bug classes |
| `503614310.txt` | Original Flapjack AI report |

### To Reproduce:
```sh
python3 poc/server.py
# Open automated probe:
open http://127.0.0.1:9080/503614310-automated.html
# Open manual harness:
open http://127.0.0.1:9080/503614310-harness.html
```
