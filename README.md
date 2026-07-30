# TOCTOU Permission Race — Arc Browser PoC

Commit-on-Close origin misattribution in Chromium's ContentSettingBubbleModel.

## Live PoC

**https://telojos11.github.io/arcjos/**

- Part 1: Automated race window probe (zero interaction, runs in browser)
- Part 2: Interactive permission race (requires camera blocked on two origins)

## Local testing (full harness)

```sh
python3 poc/server.py
open http://127.0.0.1:9080/503614310-harness.html
```

## Reference

- crbug 503614310 — TOCTOU in ContentSettingMediaStreamBubbleModel
- Fix: commit r1617514 (Apr 2026) — MediaStream model only
- 5 other ContentSetting models may share the same uncached-origin pattern
