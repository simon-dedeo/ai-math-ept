# Human-written formal proof corpora — census summary

Location: `~/ai_math_ept/census/human/` on akdeniz.lan.cmu.edu
Manifest: `~/ai_math_ept/census/MANIFEST_human.tsv` (27 corpora + header)
Collected: 2026-07-31. All clones `--depth 1`; commit histories then re-fetched with
`--filter=tree:0` for AI-provenance grepping (no blobs/trees pulled, cheap).
No builds run: no `.lake`, `_build`, `*.olean`, `*.vo` anywhere.

**Disk used: 1.1 GB** (budget was ~20 GB). Largest: afp 708 MB, mathlib3 73 MB,
theorem_proving_in_lean4 71 MB (book assets), ConNF 65 MB, coq-stdlib 33 MB.
Machine free space after collection: 544 GB.

Not re-cloned (already on machine): mathlib4 (`~/ai_math_ept/mathlib4`, incl. `Archive/`
and `Counterexamples/`), compfiles, pfr, FLT, Sphere-Packing-Lean, PrimeNumberTheoremAnd,
equational_theories, Tao's analysis.

---

## 1. Totals per proof assistant

| assistant | corpora | proof files | lines | theorem/lemma declarations |
|---|---:|---:|---:|---:|
| Lean 4    | 15 | 2,069 | 471,757 | 21,975 |
| Lean 3    | 2  | 3,478 | 1,132,448 | 98,938 |
| Coq/Rocq  | 9  | 2,384 | 934,085 | 47,984 (36,860 `Qed`/`Defined`) |
| Isabelle  | 1 (AFP, 1,010 entries) | 10,351 | 6,101,054 | 311,123 |
| **total** | **27** | **18,282** | **8,639,344** | **480,020** |

Counting conventions: Lean = lines matching `^(attrs/modifiers)* (theorem|lemma)`;
Coq = `Lemma|Theorem|Corollary|Proposition|Fact|Remark`, plus a separate `Qed|Defined`
count which is the better proxy for *proofs* (ssreflect proves many results with
`by ...` one-liners that still end in `Qed`); Isabelle = `lemma|theorem|corollary|proposition`.
These are upper bounds on "proofs": they include statements re-proved in `Section`
contexts and exclude `Definition`/`instance` proof obligations.

## 2. Totals per subject area

| subject area | corpora | lines | theorems |
|---|---|---:|---:|
| general math libraries | mathlib3, math-comp, coq-stdlib | 1,490,315 | 127,395 |
| analysis (harmonic, functional, constructive, sci-computing) | carleson, BonnAnalysis, corn, SciLean | 330,451 | 11,909 |
| combinatorics + additive combinatorics | LeanAPAP, ExponentialRamsey, fourcolor | 70,178 | 4,077 |
| number theory (algebraic + analytic) | FLT-regular, unit-fractions | 16,825 | 768 |
| logic / set theory / ordinals | ConNF, hydra-battles | 144,235 | 6,844 |
| geometry + topology | GeoCoq, sphere-eversion | 176,366 | 5,567 |
| group theory | odd-order | 40,549 | 1,062 |
| algebra / linear algebra | math-classes, lean-matrix-cookbook | 23,839 | 1,168 |
| competition + named theorems | mathlib4-Archive, coq-100-theorems | 18,471 | 963 |
| pathologies / counterexamples | mathlib4-Counterexamples | 5,549 | 317 |
| mathematical physics | PhysLean | 186,773 | 9,108 |
| teaching / textbook | mathematics_in_lean, theorem_proving_in_lean4, math2001 | 34,739 | 719 |
| AFP (mixed) | afp | 6,101,054 | 311,123 |

AFP internal split (by first topic tag, .thy files): Mathematics 370 entries / 1,896,514 lines /
95,635 lemmas; Computer science 482 / 3,430,426 / 172,322; Logic 134 / 678,578 / 36,751;
Tools 24 / 95,536 / 6,415. AFP entry dates span **2004-2026** with ~700 distinct authors —
by far the best axis for era and author variation.

## 3. Control-group purity (AI-provenance audit)

Full commit histories were fetched (`--filter=tree:0`) and grepped for
`copilot|chatgpt|gpt|claude|anthropic|aristotle|autoformaliz|deepseek|llm|ai-generated|alphaproof|gemini|agent|auto-task`.

- **Clean (0 real hits): 24 of the 26 audited corpora**, including every Coq corpus, mathlib3
  (18,271 commits), ConNF, sphere-eversion, LeanAPAP, ExponentialRamsey, unit-fractions,
  math-comp, odd-order, fourcolor, GeoCoq, corn, coq-stdlib (45,211 commits).
- **carleson — 1 contaminated commit**: `625110462eb6` "Proved RCLike.induction with
  Aristotle (#539)" (Harmonic Aristotle). Drop that lemma for a strict control.
- **PhysLean — NOT CLEAN.** Ships `AI-POLICY.md` + `AGENTS.md` explicitly welcoming
  AI-assisted PRs, and carries 27 `auto-task(...)` commits from an agent-driven task
  workflow (mostly 2026-06 onward). **Recommendation: exclude PhysLean from the human
  control**, or restrict to pre-2026-06 content.
- False positives filtered out: contributors named Clement Pit-Claudel, Claude Stolze,
  Claude Marche; `leanprover-community-bot` / `coqbot-app[bot]` dependency-bump and merge
  commits; "harmonic oscillator" (PhysLean/SciLean physics content).
- AFP history not grepped (50k+ commit mirror, shallow clone); AFP requires named human
  authors and per-entry editorial review, and 947 of 1,010 entries predate 2025.
- mathlib4 `Archive/` and `Counterexamples/` inherit mathlib PR policy (undisclosed
  AI-generated content disallowed) but share mathlib history, so were not separately audited.

**Cleanest sub-corpus by construction**: everything written before ~2023 — mathlib3 (frozen
2023-10), unit-fractions (Lean 3), corn, coq-stdlib, GeoCoq, fourcolor, odd-order, math-comp,
and AFP entries dated 2024 or earlier. These cannot contain LLM contamination.

## 4. Matching to the AI corpora already collected

The AI side (`~/ai_math_ept/corpora/`) contains two structurally different populations, and
they need **different** human controls.

### (a) AI *competition-proof* corpora
DeepSeek-Prover-V2 miniF2F (438 files), Kimina miniF2F (198), Goedel Lean-workbook (29,750),
NuminaMath-LEAN (31,634 proofs), AlphaProof IMO-2024 (6), Harmonic Aristotle IMO-2025 (7),
Seed-Prover IMO/miniF2F/Putnam (~200). Shape: **one self-contained theorem per file,
short-to-medium proof, no downstream dependents, statement fixed by a benchmark.**

Best human controls, in order:
1. **compfiles** (already on machine) — 333 human Lean 4 solutions to IMO/USAMO/Putnam/AMC
   problems, many literally the same items as miniF2F. Same assistant, task and era.
2. **mathlib4 `Archive/`** — `Imo/` (54 files, 8,631 lines) and `Wiedijk100Theorems/`
   (14 files, 2,940 lines): human competition/named-theorem proofs at library standard.
3. **coq-100-theorems** (10 files, 137 `Qed`) — same *theorem list* as Wiedijk100Theorems in a
   different assistant: the natural assistant-effect control.
4. **lean-matrix-cookbook** (19 files, 379 lemmas) — many short, independent identity proofs;
   a good structural analogue of one-shot benchmark proofs when more N is needed.
5. **math2001** (234 lemmas, elementary) — matches the *difficulty floor* of miniF2F
   (AMC/AIME level), which compfiles and Archive/Imo do not cover.

Size caveat: the human competition pool totals ~500-800 proofs against tens of thousands of AI
ones. Comparisons must subsample the AI side or work per-proof rather than per-corpus.

### (b) AI *project-formalization* corpora
math-inc Sphere-Packing-Lean (Gauss, 830 files / 180k lines), math-inc strongpnt (8 files /
28k lines), alphaproof-nexus (71 research-level proofs), Seed-Prover miniCTX-v2 (545
repo-context proofs). Shape: **large multi-file developments with a dependency DAG,
blueprint-driven, results reused downstream** — the same shape as the 2022 paper's networks.

| AI corpus | closest human control | why |
|---|---|---|
| Sphere-Packing-Lean (Gauss; Fourier analysis, modular forms, 180k lines) | **carleson** (48.8k lines, 2,592 thms) + **sphere-eversion** (14.6k) + the human layer of Sphere-Packing-Lean already held | Same subject family (harmonic/Fourier analysis), same blueprint-driven multi-file style, same Lean 4 era. carleson is the single best match. |
| strongpnt (Gauss; strong PNT, 28k lines) | **PrimeNumberTheoremAnd** (already held), then **unit-fractions** (12.4k lines, Lean 3) and **FLT-regular** | PNT& is literally the same theorem family; unit-fractions gives an analytic-NT human comparison at almost exactly strongpnt's size. |
| Seed-Prover miniCTX-v2 (proofs into carleson / ConNF / FLT / HepLean) | **the same repos' human commits**: carleson, ConNF, FLT | Strongest possible design: identical ambient library and statement pool, only the author differs. Highest-value comparison in the census. |
| alphaproof-nexus (Erdos problems, OEIS, Stacks; scattered research lemmas) | **mathlib4 Archive** + **LeanAPAP** + **ExponentialRamsey** | Research-level but self-contained human results in combinatorics and number theory. |
| any combinatorics-flavoured AI output | **LeanAPAP** (7.2k lines, 666 thms), **ExponentialRamsey** (18.2k, 1,015), **fourcolor** (44.7k, 852 Qed) | Covers additive combinatorics, Ramsey theory and graph theory across two assistants. |

### (c) Replicating the 2022 Coq-network paper
**fourcolor** (Gonthier-Werner) and **odd-order** (Feit-Thompson) are the same lineage as that
paper's four-colour and Sylow networks, and **math-comp** is their shared dependency base; the
three together allow exact reproduction of the earlier network analysis before contrasting it
with the Lean 4 AI corpora. **corn**, **GeoCoq**, **coq-stdlib** and **hydra-battles** extend the
Coq control across constructive analysis, geometry, foundations and ordinal logic.

### (d) Era and author-variation controls
- **mathlib3** (1.12M lines, 98k lemmas, frozen 2023-10) — largest guaranteed pre-LLM Lean corpus.
- **coq-stdlib** (history to 1999) and **corn** (from ~2003) — 20+ year human baselines.
- **AFP** — 1,010 entries, 2004-2026, ~700 authors: the only corpus here supporting
  author-level and year-level random effects at scale.

### (e) Use with care
- **PhysLean** — AI-assisted by policy (see section 3). Exclude, or restrict to pre-2026-06.
- **SciLean** — 86k lines but only 2,092 theorems (~24 per 1k lines); largely tactic and
  metaprogramming code, low proof density.
- **mathematics_in_lean / theorem_proving_in_lean4 / math2001** — teaching-level; contain
  exercise stubs with `sorry` that must be filtered out. Useful only as a difficulty-floor control.
