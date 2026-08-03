#!/bin/bash
cd ~/ai_math_ept/census || exit 1
c(){ slug=$1; url=$2; shift 2
  if [ -d "$slug/.git" ]; then echo "SKIP $slug"; return; fi
  git clone --depth 1 --quiet "$url" "$slug" 2>&1|tail -2
  [ -d "$slug/.git" ] && echo "OK $slug $(du -sh $slug|cut -f1)" || echo "FAIL $slug"
}
c coq-modeling-results  https://github.com/rkthomps/coq-modeling
c dsp-isabelle          https://github.com/albertqjiang/draft_sketch_prove
c metagen-metamath      https://github.com/princeton-vl/MetaGen
c holophrasm-metamath   https://github.com/dwhalen/holophrasm
c setmm-gptf            https://github.com/metamath/set.mm
c tactician-benchdata   https://github.com/coq-tactician/benchmark-data
