#!/bin/bash
# Extracts text from a print-to-PDF artifact and asserts the cross-origin leak.
# Usage: ./verify.sh <saved.pdf> [expected-secret]
set -u
PDF="${1:?usage: verify.sh <saved.pdf> [expected-secret]}"
SECRET="${2:-SUPERSECRET-TOKEN-12345}"
DIR="$(cd "$(dirname "$0")" && pwd)"
TXT="$(swift "$DIR/evidence/extract-pdf-text.swift" "$PDF" 2>&1)"
echo "$TXT"
echo "--------------------------------------------------"
fail=0
if grep -q "$SECRET" <<<"$TXT"; then
  echo "PASS  embedder's query string reached origin B's rendered output"
else
  echo "FAIL  secret not found (headers/footers disabled in the preview?)"; fail=1
fi
if grep -q "localhost:8081\|origin B" <<<"$TXT"; then
  echo "PASS  body content is origin B's"
else
  echo "FAIL  body is not origin B's - did you print the top page instead of the iframe?"; fail=1
fi
exit $fail
