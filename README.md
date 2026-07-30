# arcjos — Chromium Browser Security Research

Two cross-origin boundary violations in Chromium's print and permission subsystems.

---

## Finding 1: Print Preview Cross-Origin URL/Title Leak

**Severity**: Low–Medium (site isolation boundary violation)

When a cross-origin `<iframe>` calls `window.print()`, the browser sends the **embedder's full URL** (including path and query string) and **title** into the subframe's renderer process for the print header/footer. Same-origin policy explicitly blocks `top.location.href` and referrer policy strips the URL to origin-only — the print path bypasses both.

**Confirmed in Arc browser**: `evidence/evidence-Arc-print-leak.pdf`

### Reproduce
```sh
python3 poc/server.py
# Open: http://127.0.0.1:9080/top.html?session=SUPERSECRET-TOKEN-12345&user=admin
# Click "window.print()" inside the iframe → Save as PDF with headers/footers on
# Verify: ./verify.sh <saved>.pdf
```

→ Report: `HACKERONE_PRINT_LEAK.md`

---

## Finding 2: TOCTOU Permission Spoofing via Async Widget Teardown

**Severity**: High (camera/mic/geo/notifications/clipboard theft)

A commit-on-close TOCTOU pattern across `ContentSettingBubbleModel` subclasses allows an attacker page to steal **persistent permissions** the user intended for a different origin. The race: BLOCK-state permission callbacks resolve synchronously, overwriting the origin before the asynchronous bubble teardown completes.

**Confirmed race window in Arc/Chrome**: `poc/503614310-automated.html`

### Reproduce
```sh
python3 poc/server.py
# Automated probe (no interaction): http://127.0.0.1:9080/503614310-automated.html
# Manual harness: http://127.0.0.1:9080/503614310-harness.html
```

→ Report: `HACKERONE_TOCTOU_RACE.md`
→ Threat model: `THREAT_MODEL.md`
→ Impact: `SECURITY_IMPACT.md`

---

## Files

```
.
├── HACKERONE_PRINT_LEAK.md      # Print header cross-origin leak report
├── HACKERONE_TOCTOU_RACE.md     # TOCTOU permission race report
├── THREAT_MODEL.md              # 5 bug classes derived from pattern
├── SECURITY_IMPACT.md           # Attack flow + impact assessment
├── 503614310.txt                # Original Flapjack AI finding
├── verify.sh                    # Print leak verification script
├── poc/
│   ├── server.py                # Dual-origin test server (9080 + 9081)
│   ├── 503614310-automated.html # Auto probe (zero interaction)
│   ├── 503614310-harness.html   # Interactive 5-tab race harness
│   ├── 503614310-race.html      # Race payload page
│   ├── top.html, frame.html ... # Print leak PoC files
├── evidence/
│   ├── evidence-Arc-print-leak.pdf  # Arc browser confirmed leak
│   ├── evidence-A/B/C/D-*.pdf       # Chrome confirmed leaks
│   ├── evidence-A/B/C/D-extracted.txt  # PDF text extractions
│   ├── extract-pdf-text.swift     # PDFKit-based text extractor
│   └── pdfx.py                    # Raw PDF string extractor
```

## Status

| Finding | Status |
|---------|--------|
| Print preview URL leak | **Unfixed, unreported** — STAY PRIVATE |
| TOCTOU MediaStream race | Fixed (r1617514) — other subclasses unknown |
| TOCTOU Geo/Notify/Clipboard race | **Untested** — same pattern, may be unfixed |
