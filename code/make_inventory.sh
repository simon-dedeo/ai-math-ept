#!/bin/bash
# make_inventory.sh — enumerate the bulk data on akdeniz so reviewers can see
# what exists (and how big it is) without ssh access. Run from a machine with
# ssh to akdeniz; writes results/DATA_INVENTORY.md in this repo.
set -u
OUT="$(cd "$(dirname "$0")/.." && pwd)/results/DATA_INVENTORY.md"
{
  echo "# Data inventory — akdeniz.lan.cmu.edu:~/ai_math_ept/"
  echo
  echo "Generated $(date '+%Y-%m-%d %H:%M'). Bulk data is not in git; this is the manifest."
  echo
  ssh akdeniz.lan.cmu.edu 'cd ~/ai_math_ept 2>/dev/null || exit 0
    echo "## Totals"; echo
    echo "| top-level | size |"; echo "|---|---|"
    for d in */; do printf "| %s | %s |\n" "${d%/}" "$(du -sh "$d" 2>/dev/null | cut -f1)"; done
    echo; echo "Disk: $(df -h / | tail -1 | awk "{print \$4\" free of \"\$2}")"
    echo
    echo "## Corpora (proof-file counts)"; echo
    echo "| corpus | .lean files | dir |"; echo "|---|---|---|"
    for d in corpora/*/ census/*/ census/hf/*/ census/human/*/ projects/*/; do
      [ -d "$d" ] || continue
      n=$(find "$d" -name "*.lean" -not -path "*/.lake/*" 2>/dev/null | wc -l)
      t=$(find "$d" \( -name "*.thy" -o -name "*.v" \) 2>/dev/null | wc -l)
      tot=$((n+t))
      [ "$tot" -gt 0 ] && printf "| %s | %s | %s |\n" "$(basename "$d")" "$tot" "$d"
    done
    echo
    echo "## Extracted networks"; echo
    echo "| network set | JSON/edge files |"; echo "|---|---|"
    for d in networks/*/; do
      n=$(ls "$d" 2>/dev/null | wc -l)
      [ "$n" -gt 0 ] && printf "| %s | %s |\n" "$(basename "$d")" "$n"
    done
  '
} > "$OUT"
echo "wrote $OUT"
