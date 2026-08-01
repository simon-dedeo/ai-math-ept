#!/bin/bash
# sync.sh — mirror akdeniz working results into this repo and push.
# Bulk data is mirrored separately into Git-ignored local directories; this
# lightweight helper pulls versioned code and derived results and then pushes.
set -u
REPO="$(cd "$(dirname "$0")" && pwd)"
REMOTE=akdeniz.lan.cmu.edu:ai_math_ept
cd "$REPO"

echo "[sync] pulling code…"
rsync -a --delete --exclude='__pycache__' --exclude='*.pyc' \
      "$REMOTE/code/" code/
echo "[sync] pulling results…"
rsync -a --max-size=40M --exclude='curves/*.json' "$REMOTE/results/" results/

# census manifests are small and worth versioning even though the data is not
mkdir -p results/census_manifests
rsync -a --include='*/' --include='MANIFEST*' --include='SUMMARY*' --exclude='*' \
      "$REMOTE/census/" results/census_manifests/ 2>/dev/null || true

if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git -c user.name="Simon DeDeo" -c user.email="sdedeo@andrew.cmu.edu" \
      commit -q -m "sync from akdeniz: $(date '+%Y-%m-%d %H:%M')

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
  git push -q origin main && echo "[sync] pushed."
else
  echo "[sync] nothing new."
fi
