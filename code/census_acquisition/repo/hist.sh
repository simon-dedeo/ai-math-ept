#!/bin/bash
cd ~/ai_math_ept/census/human || exit 1
for d in */; do
  s="${d%/}"
  [ "$s" = "afp" ] && continue
  [ -d "$s/.git" ] || continue
  cd "$s" || continue
  if [ -f .git/shallow ]; then
    git fetch --filter=tree:0 --unshallow -q 2>/dev/null || git fetch --unshallow -q 2>/dev/null
  fi
  n=$(git log --oneline 2>/dev/null | wc -l)
  hits=$(git log --all --format='%H|%an|%s' 2>/dev/null | grep -icE 'copilot|chatgpt|gpt-4|gpt4| gpt |claude|anthropic|aristotle|autoformaliz|deepseek|llm-generated|ai-generated|AlphaProof|Gauss ' )
  echo -e "HIST\t$s\t$n\t$hits"
  if [ "$hits" -gt 0 ]; then
    git log --all --format='%H|%an|%s' 2>/dev/null | grep -iE 'copilot|chatgpt|gpt-4|gpt4| gpt |claude|anthropic|aristotle|autoformaliz|deepseek|llm-generated|ai-generated|AlphaProof|Gauss ' | head -8 | sed "s/^/SAMPLE\t$s\t/"
  fi
  cd ..
done
echo "HIST_DONE"
