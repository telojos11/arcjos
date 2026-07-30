# TOCTOU Permission Spoofing — Arc Browser PoC

**Commit-on-Close Origin Misattribution in Chromium ContentSettingBubbleModel**

A TOCTOU race condition allows a cross-origin attacker page to steal persistent camera, microphone, geolocation, notifications, and clipboard permissions that the user intended for a different origin.

## Reproduce in Arc Browser

```sh
python3 poc/server.py
```

This serves two origins: `127.0.0.1:9080` (attacker) and `localhost:9081` (victim).

### Automated Probe (zero interaction)
```
http://127.0.0.1:9080/503614310-automated.html
```
8 automated tests proving the race window exists in Chromium's event loop.

### Interactive Race Harness
```
http://127.0.0.1:9080/503614310-harness.html
```
5 tabs: Camera, Geolocation, Notifications, Timing, Impact. Follow the numbered steps.

## Attack Summary

1. Victim visits attacker's page → blocks camera permission (cautious behavior)
2. Attacker opens popup to trusted site, victim sees blocked camera icon
3. Victim opens permission bubble, selects "Always allow [trusted site]", pauses
4. **Race**: attacker navigates popup to attacker origin during async bubble teardown
5. BLOCK-state callbacks resolve synchronously → permission origin overwritten
6. Attacker origin gains persistent permission the user never intended to grant

**Impact**: Camera surveillance, microphone eavesdropping, GPS tracking, push notification phishing, clipboard credential theft.

## Files

| File | Purpose |
|------|---------|
| `HACKERONE_TOCTOU_RACE.md` | H1 report ready for submission |
| `SECURITY_IMPACT.md` | Attack flow + realistic GitHub Pages scenario |
| `THREAT_MODEL.md` | 5 bug classes from the commit-on-close pattern |
| `503614310.txt` | Original Flapjack AI finding (crbug reference) |
| `poc/503614310-automated.html` | Zero-interaction race window probe |
| `poc/503614310-harness.html` | Interactive 5-tab attack harness |
| `poc/503614310-race.html` | Race payload (auto-triggers permission API) |
| `poc/server.py` | Dual-origin test server |

## Status

| Permission Model | Fix Status |
|-----------------|------------|
| MediaStream (Camera/Mic) | Fixed (r1617514, Apr 2026) |
| Geolocation | **Unknown** — same pattern |
| Notifications | **Unknown** — same pattern |
| Clipboard | **Unknown** — same pattern |
| MIDI SysEx | **Unknown** — same pattern |
| File System Access | **Unknown** — same pattern |
