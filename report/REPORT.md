# How Proofs Combine in the Age of AI
## Extending "Epistemic phase transitions in mathematical proofs" to machine-generated mathematics

*Working report, 31 July 2026. Analysis code and all extracted networks: `akdeniz.lan.cmu.edu:~/ai_math_ept/`.*

---

## 0. Summary of what was done

Viteri & DeDeo (2022) modeled proofs as networks of claims and showed that human mathematical
certainty is a *collective network effect*: heavy-tailed reuse ("tinkering", out-degree α ≈ 2) plus
modularity give a proof many independent evidentiary paths, and bidirectional (deductive+abductive)
belief propagation on such networks undergoes an **epistemic phase transition** (EPT) to
near-certainty at realistic single-step error rates.

We rebuilt that entire pipeline for the AI era and ran five studies:

1. **Study 1 — Replication across 4 years and a change of proof assistant.** A Lean 4 analog of the
   CoqAST pipeline (proof-term subterm-DAGs with structural sharing, level-by-level definition
   expansion, 10k-node truncation) applied to 33 classic and frontier theorems in Mathlib 2026,
   *plus* a same-pipeline re-analysis of the original 49 Coq networks (recovered from
   `scottviteri/ManipulateProofTrees` — node counts match Table 1 of the paper exactly).
2. **Study 2 — Matched human vs. AI proofs of the same theorems.** Proof networks extracted from
   verified prover outputs (DeepSeek-Prover-V2, Kimina, Seed-Prover, AlphaProof IMO'24 raw+polished,
   AlphaProof "Nexus" research corpus, Harmonic Aristotle IMO'25) against the human control
   (306 compfiles competition proofs; Mathlib itself).
3. **Study 3 — Gauss vs. the humans it "finished."** Source-level census of Math Inc.'s Gauss
   contribution to Sphere-Packing-Lean (PR #341, +52,187 lines, still unmerged) and strongpnt,
   against the human team's pre-Feb-2026 layer.
4. **Study 4 — The Equational Theories Project as a new kind of mathematical object.** Structure,
   provenance, epistemic percolation, and (4b) a difficulty census from the complete 22,028,942-pair
   Vampire ATP dump.
5. **Study 5 — All of Mathlib as one proof network** (633,364 declarations, 10.9M edges), in two
   layers: the explicit citations a human reads vs. the full kernel-elaborated dependency structure.

**The through-line: machine-generated mathematics is verifiable without being accumulable.** Human
mathematical practice builds networks that *absorb* error — redundant, modular, heavy-tailed in
reuse — and it is that structure, on the 2022 account, that produces both certainty and
understanding. Machine-checked mathematics does not need it in order to be correct, and measurably
invests less in it: AI-authored corpora draw on a narrower vocabulary within each proof and
contribute far less reusable structure back to the library. The sharpest single demonstration is
inside one project (§5d): the machine-generated files of the Equational Theories Project have 98.3%
of declarations never cited and reach belief 0.54 under the 2022 model, while the human-written
files of the *same* project sit at 45.6% and 0.99.

Two claims we tested and had to give up are worth stating up front, because they sharpen the rest.
Individual AI proof *terms* are not structurally degenerate — if anything they are more concentrated
on library hubs than human ones (§2). And the Equational Theories skeleton is not epistemically
fragile under the belief model, only under strict derivability semantics (§5a). The deficit is not
in any single proof. It is in what a corpus leaves behind.

---

## 1. Study 1: The 2022 findings replicate — human formal mathematics still tinkers

**Method.** `ExtractNetwork.lean` reproduces the CoqAST→DAG pipeline inside Lean 4/Mathlib
(commit 6ecc792, 2026-07-31): elaborated proof terms are walked as subterm-DAGs (structural sharing =
node identity, as in the 2022 dedup), referenced theorems/defs expanded level-by-level (axioms,
inductives, constructors not expanded), truncated at the first expansion exceeding 10,000 nodes.
Same belief model (asymmetric Ising, MH heuristic, p_prior = 0.75, ~10N updates), same estimators
(CSN power-law fits; modularity; ΔL₁ firewalls; f₂ = belief in theorem at ε = 0.01).

**Calibration first — reproduction, and what it took.** We recovered the original 49 Coq ProofDAGs
and ran them through the *same* pipeline as the new Lean networks. 47 of 49 match a published
Table 1 row by exact node count (174,597 / 28,984 / 24,137 / …), confirming both the data and our
depth-selection rule.

Reproducing the published α values turned out to be a question about the estimator, and the answer
is instructive. Clauset–Shalizi–Newman select x_min *dynamically*, by minimizing the KS distance;
using that (via the `powerlaw` package) we could not reproduce Table 1 at all — per-theorem
correlation r = −0.11. The reason is visible once you look at what the KS rule chooses on these
degree sequences: **x_min ≈ 1** (median 1, range 1–9). The whole out-degree distribution is
power-law-like, so KS is minimized by including everything — and a tail index measured from x_min = 1
is a different statistic from one measured on the tail proper.

Sweeping *fixed* x_min with an explicit discrete MLE identifies the band that reproduces the paper:

| x_min | 1 | 5 | 9 | **10** | 13 | 20 | 50 |
|---|---|---|---|---|---|---|---|
| mean α | 1.95 | 2.20 | 2.16 | **2.16** | 2.15 | 2.14 | 2.13 |
| mean abs. deviation from published | 0.218 | 0.080 | 0.034 | **0.014** | 0.041 | 0.087 | — |
| correlation with published | −0.36 | 0.63 | 0.90 | **0.90** | 0.91 | 0.72 | — |

At x_min ≈ 10 the reproduction is essentially exact: **40 of 47 networks within 0.010 of the
published value, 43 within 0.020** (Euclid 2.138 vs 2.14; Gödel 1.985 vs 1.98; Pythagoras 1.938 vs
1.93; the one outlier is the smallest network, N = 739, where x_min = 10 leaves no tail).
**Table 1 of Viteri & DeDeo (2022) reproduces** — under a fixed tail cutoff, not under KS-selected
x_min.

We should not over-claim that x_min = 10 *was* the original convention. Asking each network which
x_min would exactly reproduce its published α gives a broad spread (median 18, IQR 10–54), because
α varies only slowly with x_min across this band — which is itself evidence that these are decently
power-law-like distributions. What is solid: the published numbers are tail indices at a fixed
cutoff of order 10, they are not KS-auto values, and **any α reported for a proof network should be
quoted with its x_min, since the two conventions differ by ~0.2 and correlate at zero.**

**Results, with x_min sensitivity made explicit.** Every one of the 33 Lean networks shows an
epistemic phase transition (ε_crit 0.03–0.20), reaches f₂ = 0.986 ± 0.02 at ε = 0.01, and has
Q = 0.71 ± 0.02 — matching the original Coq networks re-analyzed identically (f₂ 0.994 ± 0.017,
Q 0.715 ± 0.061; Q difference p = 0.36). The 2022 results replicate across proof assistant, four
years, and a tenfold larger library.

For α the comparison depends on where the tail is cut, and that dependence is itself the finding:

| x_min | 5 | 9 | 10 | 13 | 20 | 50 |
|---|---|---|---|---|---|---|
| Coq 2022 | 2.190 | 2.148 | 2.151 | 2.145 | 2.144 | 2.187 |
| Lean 2026 | 2.175 | 2.096 | 2.098 | 2.063 | 2.012 | 1.962 |
| p | 0.56 | 0.10 | 0.12 | 0.006 | 7×10⁻⁵ | 2×10⁻⁷ |

Coq and Lean proofs are indistinguishable in the *near* tail and diverge in the *far* tail, where
Lean's index falls to 1.96. Lower α means a heavier tail, so modern Mathlib-based proofs lean
**more** heavily on a small set of super-reused workhorse lemmas than the older Coq proofs did. That
is a signature of library maturity — a large, well-factored library concentrates usage on its hubs —
and it is the opposite of the "automation thins out reuse" story an earlier draft of this report
told. That draft's claim rested on KS-auto α values and is withdrawn.

Two further observations:

- **Frontier human formalization looks classical.** `fermatLastTheoremThree` (the largest network
  extracted, N = 36,592) has α = 2.47, Q = 0.73, f₂ = 1.0 — the deep end of modern human-led
  formalization has exactly the tinkering-and-reuse structure of Euclid and of the 2022 Coq corpus.
- **A steeper-tail cluster (α ≈ 2.9) that is all elementary number theory** (Wilson, Fermat's little
  theorem, quadratic reciprocity, FTA, harmonic divergence). These are precisely the areas where
  Lean's computational automation (`decide`, `norm_num`, kernel reduction) substitutes computation
  for lemma reuse.


### 1a-bis. The hand-coded human networks, recovered

The five human proof networks of the 2022 paper — hand-coded from original texts and never
published — were located in the original working archive. Converted with the same pipeline
(one line per claim, followed by its premises; bracketed items are external citations and are
genuine nodes), they reproduce the published sizes closely; the residual differences reflect
file-version and cleaning details we could not fully reconstruct:

| network | our N | published N | our α | published α |
|---|---|---|---|---|
| Orlik & Strauch (*Jordan–Hölder*) | **61** | 61 | 3.02 (x_min 2) | 2.14 |
| Wiles, Fermat's Last Theorem | 148 | 142 | **3.46** (x_min 3) | **3.39** |
| Herstein, *Topics in Algebra* | 303 | 280 | 2.78 (x_min 2) | 2.36 |
| Apollonius, *Conics* | 452 | 446 | **2.37** (x_min 3) | 2.28 |

(These networks are 60–450 nodes, far too small for the x_min ≈ 10 convention of §1; their tails
support only x_min of 2–3, which is presumably why the published error bars on them are large —
Wiles is quoted as 3.39 ± 0.72.)

**The paper's most distinctive human result reproduces.** Wiles's proof is the outlier of the 2022
dataset — a markedly steeper tail than any other network, which the paper reads as "a thinner
network structure… a deficit of high-degree nodes… that frustrates an epistemic phase transition."
Our independent re-analysis gives α = 3.46 against the published 3.39. Apollonius likewise lands at
2.37 against 2.28.

**A bonus the paper never used: Spinoza.** The archive also contains a hand-coded network of
Spinoza's *Ethics* (`spinoza_by_hand.txt`) — 578 nodes, 1,553 dependency edges, the *more geometrico*
deductive structure of a 17th-century work of metaphysics. Its reuse tail is **α = 2.39** (x_min 3),
squarely inside the range of the mathematical proofs (Apollonius 2.37, and the Coq corpus at
2.27 ± 0.14). A non-mathematical axiomatic system, built by a philosopher with no access to
mathematical practice as we know it, has the same tinkering-and-reuse signature. That is direct
evidence for the closing speculation of the 2022 paper — that these network properties belong to
justification in general, not to mathematics in particular.

### 1b. Is the heavy-tailed-reuse claim real? A validation against null models

Fitting an α is not the same as establishing a model. We ran three checks on the paper's own 49
networks.

**Model comparison** (Clauset–Shalizi–Newman likelihood ratios on the out-degree):

| power law vs | favoured | rejected | inconclusive |
|---|---|---|---|
| exponential | **47 / 47** | 0 | 0 |
| stretched exponential | 33 | 0 | 14 |
| lognormal | 4 | **11** | 32 |

The distribution is decisively heavy-tailed — the power law beats an exponential in *every* network.
But **"power law" specifically is not established against a lognormal**: in 11 of 47 networks the
lognormal fits better and in 32 the comparison is inconclusive. This is the standard caveat for
power-law claims and it applies to the 2022 α values as much as to ours. The defensible statement
is "heavy-tailed reuse with tail index near 2," not "the out-degree is a power law."

**Discrimination against a null.** Is α ≈ 2.2 a property of proofs or of the estimator? Fitting the
same estimator to three degree sequences per network:

| sequence | α |
|---|---|
| out-degree (claimed heavy-tailed) | **2.270 ± 0.136** |
| in-degree (claimed Poisson) | 2.461 ± 0.195 |
| size- and density-matched random DAG | 2.746 ± 0.131 |

Real out-degree tails are significantly heavier than matched random DAGs, and heavier than the
in-degree of the same networks. **The heavy tail is a fact about proofs, not an artifact of the
fit** — the paper's tinkering-and-reuse claim survives its null model.

**Independent paths**, the estimator-free quantity the EPT mechanism actually needs: real proof DAGs
average 1.04 edge-disjoint paths between reachable pairs with 3.8% of pairs having ≥2, against 1.01
and 1.3% for matched random DAGs (Wilcoxon p = 10⁻⁴). Real proofs carry significantly more path
redundancy than chance — but the absolute level is low, and (per §5a) it does not separate classical
proofs from the ETP skeleton. Our earlier claim that path disjointness "does not distinguish these
objects" was too strong: it distinguishes real from random, just not human from machine.

## 2. Study 2: AI provers vs. humans on the same theorems

**First result, and it reverses the naive prediction.** Fitting the out-degree tail of every
extracted proof network under the paper's convention (and checking every x_min from 5 to 50), human
and AI proofs differ robustly — but AI proofs have *heavier* tails, not thinner ones:

| x_min | 5 | 9 | 10 | 13 | 20 | 50 |
|---|---|---|---|---|---|---|
| human (compfiles, n = 306) | 2.225 | 2.205 | 2.197 | 2.186 | 2.159 | 2.170 |
| AI provers (n = 506; DeepSeek-V2, Kimina, Seed, Nexus) | 2.205 | 2.152 | 2.155 | 2.153 | 2.131 | 2.117 |
| Mann–Whitney p | 0.005 | 4×10⁻⁹ | 4×10⁻⁶ | 6×10⁻⁴ | 2×10⁻⁴ | 5×10⁻⁶ |

Lower α = heavier tail = usage concentrated on fewer, more dominant lemmas. This is the *same*
phenomenon Study 3 finds in the source: AI proofs draw on a **40% narrower Mathlib vocabulary** at
equal citation density. Within a single proof they lean hard on a small repertoire of workhorse
lemmas, while human proofs spread their citations across a broader base.

So the original hypothesis H1 — "AI proofs will show less reuse, hence thinner tails" — is wrong at
the level of the elaborated proof term. What AI proofs lack is not reuse of the *existing* library
(they reuse it more concentratedly than humans do), but the production of *new* reusable structure:
the deficit shows up when we ask what a corpus contributes back (§3, §5b, §5d), not what it consumes.


Corpora extracted to networks (all proofs machine-verified by their authors, elaborated and
re-checked here during extraction): DeepSeek-Prover-V2 miniF2F (287), Kimina-Prover (197/197),
Seed-Prover miniF2F (29) + IMO 2025, compfiles human control (306/306), AlphaProof IMO 2024
(raw agent output *and* human-polished versions), AlphaProof Nexus (research-level), Harmonic
Aristotle IMO 2025. Matching is by competition problem ID across corpora.

Micro-metrics per proof: term-DAG size, **dedup ratio** (tree size / DAG size — structural sharing
*within* a single proof, i.e. micro-tinkering), depth, distinct premises cited, expanded-network
α/Q/f₂.

## 3. Study 3: What an AI's mathematics looks like at the source level

Math Inc.'s Gauss completed the sphere-packing formalization the human team had worked on for two
years (sorry-free in ~3 weeks; the human repo still carries 74 sorries; the AI's PR #341 remains
unmerged five months later — the community is *reviewing faster than it can absorb*). Comparing the
human layer, Gauss's sphere-packing layer (6,194 new declarations), and Gauss's strongpnt:

| metric | Human (sphere) | Gauss (sphere) | Gauss (strongPNT) |
|---|---|---|---|
| lemma : theorem ratio | 1.4 : 1 | 6.7 : 1 | 13.8 : 1 |
| defs : theorems | 0.19 | 0.27 | **0.04** |
| proof lines (mean / p90) | 10.1 / 27 | 20.7 / 50 | 17.0 / 35 |
| `have` steps per proof (mean) | 1.2 | 5.2 | 4.7 |
| citations per 1,000 candidate citers | 1.31 | **0.38** | 1.30 |
| lemmas never cited in-repo (size-matched) | 24% | **67%** | 20% |
| verbatim-duplicated `have` lines | 20.1% | **29.4%** | 12.9% |
| distinct Mathlib identifiers (matched 16k-line samples) | 1,279 | 779 | 722 |
| block-level (5-line shingle) duplication | 7.9% | 5.9% | 3.4% |

The refined picture: Gauss does **not** copy-paste blocks (it duplicates *less* at block level than
humans). Its signature is **repetition-without-reuse**: it re-derives the same small facts in-line,
step by step, dozens of times, instead of naming them once and citing them. Its lemma pool is a
heap, not a library: two-thirds of what it proves is never used again even once. Its Mathlib
vocabulary is 40% narrower at equal citation density. In Viteri–DeDeo terms: **the generative
process of "tinkering and reuse" — the process that produces α ≈ 2 out-degree tails, modularity, and
hence the possibility of epistemic phase transitions — is precisely what the AI lacks.**

(The one reversal is instructive: for sphere-packing dim-24, Gauss *did* mint definitions at a
higher rate than the humans — abstraction under combinatorial duress is not impossible for these
systems, just not their default economy.)

## 4. Study 4: The Equational Theories Project — mathematics without redundancy

The ETP decided all 22,028,942 implications among 4,694 magma laws, Lean-verified. Provenance
(from `full_entries.json`): 12,084 of 12,373 result entries are machine-generated (SimpleRewrites
6,305; Vampire-replayed 1,723; brute force 1,497; finite models 926; egg 832; …) vs. **289
human-written entries (2.3%)** — and 1,698 counterexample magmas certify 13.6M non-implications.

**4a. The derivation skeleton is minimal and single-threaded.** The 8,167,622 true implications rest
on a skeleton of 10,657 direct proofs (766× amplification by transitivity). On that skeleton:
- mean derivation chain: **14.2 steps** (max 30) — longer than most human proofs;
- median number of edge-disjoint derivation paths per implied pair: **1** (mean 1.12);
- percolation under derivability semantics (fig. 1): if each certificate independently fails at
  rate ε, the fraction of derived implications still derivable is 99.8% (ε = 0.001), 95.7%
  (ε = 0.01), 88.4% (ε = 0.03), 58% (ε = 0.1).

**Two corrections we owe the reader here.** First, an earlier draft contrasted this with "the many
independent paths of classical proof networks." That contrast does not survive measurement: running
the same edge-disjoint path count on the 2022 paper's own Coq proof DAGs gives **1.04 on average**
— the same range as the ETP. (Real proofs do carry significantly more redundancy than random DAGs;
see §1b. But that redundancy does not separate classical proofs from the ETP skeleton, and we
withdraw the claim that it does.)

Second, and more importantly, percolation-of-derivability and the 2022 belief model are different
measures, and an earlier version of figure 3 plotted one against the other. Running the **belief
model itself** on the ETP skeleton (fig. 3, corrected) gives mean belief 0.976 at ε = 0.01 — below
individual theorem proofs (≈1.0) and Mathlib (0.9995), but not catastrophically, and *above*
individual proofs once ε exceeds 0.1. Under the epistemic dynamics of the original paper, the ETP
skeleton behaves like ordinary mathematics. It has mean degree 2.27 and a heavy out-degree tail
(α ≈ 2.0) — the same signature the 2022 paper found in proofs.

So the honest statement about the ETP is narrower than "machine mathematics is fragile," and more
interesting: **its derivability is single-threaded by construction, while its belief-dynamics are
ordinary.** The fragility is real but it is a property of how the knowledge is *stored* (a minimal
spanning skeleton) rather than of what it *is*. The strongest evidence for structural impoverishment
in machine-generated mathematics comes not from here but from §5d, where the machine-generated files
of this very project reach belief 0.54 under the same model.

Two further reversals of the classical picture:

- **Deductive depth became agent-relative.** The 14-step chains are an artifact of the *minimal
  recorded skeleton*; for the ATP the whole positive universe is depth-1. "Deep" vs. "shallow" no
  longer describes the mathematics; it describes a relationship between the mathematics and a
  particular prover.
- **The human contribution lives in the tail of the difficulty distribution** — and on the *false*
  side. Machines ate the entire provable head; the celebrated human work (Asterix/Obelix, Austin
  laws, greedy constructions) is exotic counterexamples. (Cf. the "effort follows the heavy tail"
  hypothesis, H8 below.)

## 5. Study 5: All of Mathlib as one epistemic object

We ran the belief dynamics on the entire Mathlib dependency graph (MathlibGraph, Feb 2026:
308,060 Mathlib declarations, 8.44M edges), in two layers:

| ε | full elaborated network (8.44M edges) | explicit human-visible citations only (2.18M edges) |
|---|---|---|
| 0.01 | mean belief **0.9995** (theorems 0.9996) | 0.956 (theorems 0.959) |
| 0.05 | 0.9993 | 0.953 |
| 0.10 | 0.9992 | 0.948 |
| 0.30 | **0.9967** | 0.911 |

Two lessons:

- **The accumulated library is an epistemic fortress.** The full network sits so far above the
  phase transition that belief is essentially total even at an absurd 30% per-step error rate —
  the polar opposite of the ETP skeleton (Study 4), on the same day, in the same proof assistant.
  What distinguishes them is *accumulation*: Mathlib is 8 years of tinkering-and-reuse by ~800
  humans; the ETP skeleton is a one-shot, efficiency-pruned machine artifact.
- **The human-visible layer alone already crosses the transition** (0.96 at realistic ε), but the
  74% of dependency edges that only the compiler sees push it to ~1. The mathematics a human
  *reads* and the mathematics the kernel *checks* are epistemically different objects — the reader
  is entitled to slightly less certainty than the machine — a quantitative rendering of the
  tracking problem.

## 5b. Study 6: Who builds the load-bearing mathematics? (ETP provenance)

Using ETP's complete provenance record (each of 10,657 direct implications attributable to a
human-written file or a specific automated pipeline), we traced 9,354 actual derivation paths
through the skeleton and measured how much derived knowledge each direct proof carries.

| provenance | n (sampled edges) | mean derivation load | median | Mann–Whitney |
|---|---|---|---|---|
| human-written (`Subgraph.lean`, `InfModel`) | 20 | **46.6** | 4.0 | p = 0.002 |
| machine (SimpleRewrites 6305, Vampire 1507, brute force 1497, egg 832, …) | 2,980 | 9.4 | 1.0 | — |

**Human-proved implications carry ≈5× the derivation load of machine-proved ones.** Machines
resolved 97.7% of the direct proofs; the human ones sit at the structural joints. This is the
sharpest available confirmation of the "machines eat the head, humans hold the load-bearing tail"
division of labor. *Caveats:* only 20 human edges landed in the sample (the effect is significant
but the estimate is coarse), and there is a partial selection tautology — humans deliberately
proved the implications they judged structurally important. That the judgment was *correct*, in
the sense that those edges carry 5× the traffic, is itself the finding.

## 5c. Study 7: The automation dose–response law is *not* supported at tactic level (N1 partly falsified)

We tested N1 inside Mathlib at 73k-theorem scale, scoring each tactic proof by the share of its
tactic invocations that are "closers" (`simp`, `decide`, `norm_num`, `omega`, `linarith`, `aesop`…)
versus structural steps, and relating that to how many named premises it cites and how often it is
later reused.

The correlations are highly significant but tiny, and the binned relation is **non-monotonic**:

| automation share | n | median explicit premises | mean reuse | never reused |
|---|---|---|---|---|
| 0–10% | 34,362 | 10 | 2.49 | 28.0% |
| 10–25% | 7,300 | 25 | 1.81 | 19.6% |
| 25–50% | 13,145 | 16 | 2.00 | 27.3% |
| 50–75% | 1,553 | 20 | 1.69 | 29.2% |
| 90–100% | 16,958 | 9 | 2.26 | **37.4%** |

Spearman(automation, reuse) = −0.056 (p = 10⁻⁵¹); size-controlled OLS β = −0.07. Only the
fully-automated extreme (median 1 tactic — one-line `simp`/`decide` proofs) stands out.

**So N1 as originally stated is wrong**: per-theorem tactic choice does *not* smoothly erode reuse.
One thing does survive, and it is the network-level measure: the sub-library built from
automation-heavy theorems is **measurably less robust** than the automation-light one
(belief 0.786 vs 0.864 at ε = 0.01). Revised N1: structural erosion is a property of *the economy
of the agent that generates a whole corpus* — what it is cheap to look up versus re-derive — not of
which tactic closes an individual goal. That is why it appears strongly between authors
(human vs Gauss, §3) and between corpora (§5d) but barely within one human library.

## 5d. Study 8: The same project, split by author, is two different worlds

Source-level named-citation graphs (no compilation, so every corpus is treated identically):

| corpus | author | decls | Q | α(reuse) | never cited | belief @ ε=.01 |
|---|---|---|---|---|---|---|
| ETP — human-written files | human | 2,153 | 0.488 | 1.91 | 45.6% | 0.989 |
| **ETP — machine-generated files** | **machine** | **11,046** | **0.145** | 2.04 | **98.3%** | **0.542** |
| sphere packing — human layer | human | 1,026 | 0.509 | 2.03 | 30.6% | 0.981 |
| sphere packing — Gauss layer | AI | 5,676 | **0.514** | 1.96 | 19.9% | 0.988 |
| strongPNT — Gauss | AI | 1,110 | 0.794 | 2.37 | 18.5% | 0.898 |
| pfr / FLT / PNT+ / compfiles | human | 1k–8k | 0.46–0.60 | 1.7–2.3 | 25–33% | 0.94–0.99 |
| Seed-Prover / Aristotle / AlphaProof-Nexus | AI | 0.1k–6k | 0.63–0.70 | 1.9–2.1 | 19–42% | 0.95–0.98 |

Two results, one confirming and one correcting:

- **The machine-generated layer of the ETP is a heap, not a library.** Inside a *single project*,
  with the same subject matter and the same period, the machine-generated files have 98.3% of
  declarations never cited, Gini 0.999, modularity 0.145, and belief 0.54 — while the human-written
  files of the very same project look like ordinary mathematics (45.6%, Q 0.49, belief 0.99). This
  is the cleanest controlled demonstration in the whole project that *machine-generated mathematics
  does not accumulate*.
- **N2 (modularity conserved) survives a real test.** Human and Gauss layers of sphere packing have
  Q = 0.509 vs 0.514 — indistinguishable — even though their reuse economies differ by 3.4× on the
  per-opportunity measure (§3). Modularity looks like it is imposed by the mathematics; reuse by
  the author.
- **Correction to §3:** at the *raw* never-cited level Gauss's layer is not worse than the humans'
  (19.9% vs 30.6%) — because it is 5.5× larger, giving every lemma more chances to be cited. The
  reuse deficit is real only on the size-normalized, per-opportunity measure. Both numbers belong in
  any honest account.

## 5e. Study 10: A census of proof corpora  ⚠️ **CORRECTED**

> **All token metrics in this section were recomputed after review found that comments and string
> literals were being tokenised. The direction of that artifact turns out to differ by corpus, so
> both the old and new numbers are given.**

Two-tier census pipeline (`code/census.py`): Tier 1 computes per-proof metrics and a corpus-level
citation graph from source with no compilation; Tier 2 is elaborated proof-term extraction. The
census covers 49 corpora — AI output from AlphaProof, Aristotle, Seed-Prover, DeepSeek-Prover
V1/V1.5/V2, Kimina, Goedel, Leanabell, STP, Lean-STaR, LeanAgent and Gauss — against 27 human
corpora spanning Lean 4, Lean 3, Coq and Isabelle's AFP. The human control was audited for
contamination (`carleson` carries one Aristotle-proved lemma; `PhysLean` welcomes AI PRs and is
excluded from strict comparisons; Lean 3 `mathlib3`, frozen October 2023, is a pre-LLM baseline).

**The comment artifact cuts both ways.** On the 27 corpora common to both runs:

| metric | before: human | before: AI | after: human | after: AI |
|---|---|---|---|---|
| vocabulary ratio | 0.700 | 0.611 | 0.667 | 0.556 |
| distinct premises | 8 | 7 | 7 | 5 |
| proof length | 10 | 12 | 9 | 9 |
| corpus-level p (vocab) | — | **0.51 (n.s.)** | — | **0.011** |

Stripping comments *widened* the gap here and made the corpus-level test significant — the opposite
of what happened in the paired corpus (§5g), where stripping *eliminated* the gap. The reason is
that comment content differs by corpus: human proofs in the NuminaMath corpus embed the
natural-language problem statement, while several AI corpora (reasoning-trace provers) embed long
model commentary. **Any token-level metric on Lean source is sensitive to this, and the bias has no
consistent sign.** That is a methodological result worth stating on its own.

Post-fix, length-stratified (Lean 4 only, 10,005 human and 191,501 AI proofs):

| proof length | 1–5 | 6–10 | 11–20 | 21–40 | 41–80 | 80+ |
|---|---|---|---|---|---|---|
| human | 0.778 | 0.733 | 0.667 | 0.579 | 0.521 | 0.427 |
| AI | 0.667 | 0.560 | 0.472 | 0.385 | 0.312 | 0.243 |

**How much weight this carries.** The census is observational: systems choose their own problems, so
authorship is confounded with domain and difficulty. It says AI corpora *as collected* show lower
vocabulary ratios at every length. It does **not** establish an authorship effect — the paired
design in §5g, which holds the theorem fixed, finds premise counts equivalent. Where the two
disagree, the paired design wins, and the census difference is most plausibly corpus composition.

## 5f. Study 11: The matched-theorem experiment — problem, not system, governs structure

Every comparison above is observational: systems choose which problems to attack, so structure and
difficulty are confounded. The Lean eval submission store breaks that confound. We harvested it —
**7,636 proof files from 428 public submission records**, covering 148 research-level problems by
37 self-reported systems, plus 168 reference statements — and restricted to problems solved by four
or more distinct systems. (The store's other 560 records were submitted privately and are
unrecoverable; the public subset is therefore a biased sample, and several "models" are
human-in-the-loop or multi-model ensembles.)

Within each problem we rank the systems on each structural metric, then ask whether those ranks are
consistent across problems. On the largest complete block, 7 problems × 7 systems:

| metric | Friedman p | Kendall W (rank concordance) |
|---|---|---|
| proof length (lines) | 4×10⁻⁵ | **0.71** |
| `have` steps | 3×10⁻⁵ | **0.73** |
| distinct premises | 4×10⁻⁴ | 0.58 |
| vocabulary ratio | 0.018 | 0.37 |

**System style is real and reproducible.** Hold the theorem fixed and the systems still order
themselves the same way, strongly so for verbosity: Humanifa+GPT-5.6 and Aristotle write the
shortest, least step-by-step proofs (mean ranks 1.4 and 2.1 of 8.6), EVO the longest and most
`have`-laden (8.6, 8.5). Verbosity is the most stable trait a prover has.

**But the theorem dominates.** Decomposing variance across 150 problem–system cells:
**between-problem 89.8%, between-system 16.4%.** What a proof looks like is overwhelmingly a fact
about the mathematics, not about who wrote it. This is the strongest evidence in the whole project
against a naive "AI proofs are different" reading — at matched difficulty, most of the apparent
difference dissolves.

**And the vocabulary effect appears to be downstream of verbosity.** Across systems, the rank
ordering on proof length predicts the rank ordering on vocabulary ratio with Spearman ρ = −0.71
(p = 0.07, n = 7 systems), and length rank predicts `have`-count rank at ρ = 1.00. The mechanism
this suggests — and it is consistent with the length-stratified population result of §5e, where
the human/AI vocabulary gap was negligible for short proofs and large for long ones — is a single
underlying trait: **some systems write long, step-by-step derivations, and vocabulary collapse
follows from length rather than being an independent signature of machine authorship.**

So *between AI systems*, style is real but the problem dominates. Whether this also explains the
human/AI difference is settled by the paired design in §5g — it does not.

### 5f-bis. Independent replication at 40× the scale

The HuggingFace census (55 datasets, 81,271 extracted proofs) supplies a second, much larger matched
set: the same benchmark problem proved by many prover systems, restricted to verified samples
(raw-generation datasets with no verification field excluded). This gives **55,512 measured proofs
from 45 systems over 39,489 problems**, of which **1,823 problems were proved by ≥3 systems**
(6,306 problem–system cells) — against the 150 cells of the lean-eval block.

The verbosity result replicates almost exactly, and the variance split replicates qualitatively:

| | lean-eval (150 cells) | HF census (6,306 cells) |
|---|---|---|
| Kendall W, proof length | 0.71 | **0.69** |
| Kendall W, vocabulary ratio | 0.37 | **0.43** |
| Kendall W, `have` steps | 0.73 | **0.07** (does not replicate) |
| variance: between-problem | 89.8% | 53.7% |
| variance: between-system | 16.4% | 25.7% |

Two conclusions are now on firm footing. **Proof length is the most rank-stable trait a prover has**
(W ≈ 0.7 in two independent corpora, different problem populations, different systems), and **the
problem still explains more structural variance than the system does** — though the system's share
is larger here (26%) than the small block suggested (16%). The `have`-step concordance does not
replicate and should be treated as an artifact of the small lean-eval block.

### 5f-ter. The missing control: how much does one system vary from itself?

Between-system differences are only interpretable against a noise floor — how much do two proofs of
the *same* theorem by the *same* system differ? The InternLM Lean-Workbook corpus answers this
directly: it ships a *list* of alternative proofs per theorem from one stepwise system. Using 1,486
theorems with ≥3 proofs each (9,196 proof samples):

| source of variance | vocabulary ratio | proof length |
|---|---|---|
| between theorems | 82.2% | 73.4% |
| **within theorem, same system (resampling)** | **17.8%** | **26.6%** |
| *(for comparison)* between systems, §5f-bis | 25.7% | 11.0% |

**For proof length, resampling one system on one theorem generates more variance (26.6%) than system
identity does (11.0%).** The within-theorem standard deviation is 0.44–0.55 of the between-theorem
standard deviation on every metric.

This sharply qualifies the "system style" result without contradicting it. Both things are true:
system *medians* order themselves consistently across problems (Kendall W ≈ 0.7 for length, in two
independent corpora), *and* the distributions overlap so heavily that a single proof is a weak
signal of its author. Style is real as a tendency and nearly useless as a classifier — which is the
same conclusion the corpus-level test reached for vocabulary ratio in §5e, arrived at by a different
route.

It also explains why the human/AI contrast needed the paired design of §5g to see cleanly: with a
noise floor this high, only holding the theorem fixed *and* comparing within-statement can resolve
an authorship effect.

## 5g. Study 12: Same statement — paired human vs AI  ⚠️ **CORRECTED**

> **This section previously reported that AI proofs cite half as many distinct library premises
> (10 → 5) at identical proof length, and called the result decisive. That was largely an artifact
> of the premise metric counting identifiers inside comments and string literals — human proofs in
> this corpus carry the natural-language problem statement in a `/- … -/` docstring, whose
> capitalised words were being counted as library references. After stripping comments and strings,
> the premise gap disappears. The corrected result is below; the original is retained in git history
> (commit `e31725d`).**

The NuminaMath proof-artifact corpus gives, per row, one formal statement with **both** a human and
a prover formal proof, each independently validated. Restricting to rows where both are present and
valid gives **2,321 matched pairs** across 12 problem sources.

Metrics are now computed on comment- and string-stripped source. We report two premise counts: a
*loose* one (dotted or capitalised identifiers, the original heuristic) and a *strict* one (dotted
identifiers only, which are unambiguously library references rather than local binders). Rather than
reading non-significance as sameness, we report bootstrap CIs on the median paired difference and an
equivalence test against a ±10% bound; and because pairs from one source are not independent, a
cluster bootstrap over source.

| metric | human | AI | median diff | 95% CI | equivalent within ±10%? | Wilcoxon p |
|---|---|---|---|---|---|---|
| proof length (lines) | 23 | 26 | +2 | [1, 2] | yes | 9×10⁻¹³ |
| tactic invocations | 12 | 11 | 0 | [0, 0] | yes | 0.008 |
| **`have` steps** | **3** | **6** | **+1** | **[0, 1]** | **no** | **3×10⁻⁴⁷** |
| distinct premises (loose) | 5 | 4 | **0** | **[0, 0]** | yes | 3×10⁻²⁴ |
| distinct premises (strict) | 3 | 2 | **0** | **[0, 0]** | yes | 6×10⁻¹⁵ |

Cluster bootstrap over the 12 sources gives the same picture: median difference 0 [0, 0] for both
premise metrics, +2 [1, 3] lines.

**What survives.** AI proofs of the same statement use about **twice as many inline `have` steps**
(3 → 6), and this is the one contrast that is *not* equivalent within the ±10% band. They are also
slightly longer (+2 lines, statistically significant but inside the equivalence bound).

**What does not survive.** The premise deficit. Distinct library premises are statistically
equivalent between human and AI proofs of the same theorem, on both the loose and the strict metric,
with and without clustering. The claim that machine proofs "touch half the library" was wrong.

**What this does to the argument.** The single-proof mechanism I proposed — *where a human reaches
for a lemma, the machine builds the step inline* — is now only half supported. The "builds the step
inline" half stands (twice the `have` steps, at equivalent premise count and near-equivalent
length). The "instead of reaching for a lemma" half does not: machines cite as many distinct results
as humans do. The honest reading is that AI proofs **decompose more finely at equal library
contact**, which is a claim about proof presentation, not about library consumption.

Note also that the Wilcoxon p-values remain tiny even where the effect is equivalent-within-bound —
with 2,321 pairs, statistical significance is nearly guaranteed and carries no information about
magnitude. The CIs are the informative quantity here.

## 6. Hypotheses: status after these studies

| # | Hypothesis | Status |
|---|---|---|
| H1 | AI proofs reuse less than human proofs of comparable content | **Split verdict.** At the elaborated proof-term level, false — AI tails are *heavier* (§2). At the source level, true at matched proof length and dramatic for long proofs (§5e). At corpus level, not significant (p = 0.51). |
| H2 | AI completions have lower modularity | **Refuted for a like-for-like layer comparison** (Study 8: Q 0.514 Gauss vs 0.509 human, same project) — but confirmed in the extreme (ETP machine files Q = 0.145) |
| H3 | Subgoal-decomposition provers (DeepSeek-V2, Seed) are structurally closer to humans than whole-proof provers | <!-- FILL from Study 2 --> |
| H4 | AI proofs are longer with lower per-step information | **Supported** (2× proof length, 4× have-steps, 29% duplicated haves) |
| H5 | AI adds lemmas but not definitions | **Mixed**: strongpnt 0.04 defs:thm (strong support); sphere-24 0.27 (reversal under combinatorial duress) |
| H6 | Verified corpora tolerate cross-module density / abandon firewalls | **Strongly supported** (Study 4: no redundancy at all; ETP as limiting case) |
| H8 | Machines eat the head of the difficulty distribution, humans keep the tail | **Confirmed & sharpened** (4b: 100% of positives one-shot ATP-provable; Study 6: human-proved implications carry 5× the derivation load, p = 0.002) |
| H9 | Generation outpaces digestion | **Supported qualitatively** (PR #341 unmerged 5 months; 74 sorries on main vs sorry-free AI branch; Tao's distillation challenge) |
| H12 | Residual epistemic risk migrates to definitions/statements | Framework result (correspondence problem); ETP + Gauss episodes consistent; not yet quantified here |

## 7. What this means for how mathematicians think — and how AI is changing it

**(i) Two epistemic regimes.** The 2022 paper showed human mathematical certainty is produced by
*error-absorbing* structure: redundant paths, modular firewalls, abductive back-flow. Everything we
measured about machine-era mathematics says it runs on *error-elimination* instead: a verifier
drives per-step ε to ~0, redundancy becomes waste, and the structures that made proofs believable —
and, on the Aaronson/gestalt view quoted in the 2022 discussion, *understandable* — stop being
produced. The EPT still happens in humans; it just no longer happens *in the artifact*. It is
outsourced to the kernel.

**(ii) The certainty–understanding decoupling is now measurable.** Verification tells you the
theorem is true; the *catalog of independent ways its parts are related* (the 2022 account of
understanding) is exactly what Gauss-style output lacks (one derivation path, no reuse, narrow
vocabulary). This gives empirical teeth to the correspondence problem: representation can be checked
by type signature, but *tracking* — does this formal object relate to the proof-idea — is precisely
a demand for the redundant, recognizable structure AI output doesn't build.

**(iii) The community response is re-humanization labor.** Golfing, refactoring, "distillation
challenges", blueprint discipline, the 5-month review of a formally-perfect PR: these are
mathematicians manually rebuilding error-absorbing (understanding-bearing) structure on top of
error-eliminated artifacts. Ochigame's "reconfiguration of labor" and Tao's generation/digestion
mismatch are the sociological face of the structural deficit measured here.

**(iv) Where belief now needs support.** In the belief-network model, removing redundancy makes
belief in any conclusion hostage to a single chain — *unless* one node (the verifier) is given
near-infinite β. That is the new topology of mathematical trust: a star network centered on the
kernel, plus a residual ring of genuinely human uncertainty about **definitions** (Commelin's
"ceci n'est pas une pipe", Seewoo Lee's "no verified way to check the statements"). Definition
nodes cannot be verified, only *believed* — they are where abduction, testimony, and stress-testing
still operate. A concrete falsifiable prediction: review attention (comments, Zulip threads,
churn) should concentrate on definition/statement nodes in AI-completed projects at a much higher
rate than in human-era formalizations.

**(v) Deep ≠ deep anymore.** Difficulty and depth became prover-relative (Study 4b). The
human-facing "depth" of a result is a fact about *our* search and reuse economies. As provers
strengthen, the mathematical universe reshuffles into "flat for the machine / structured for us,"
and value-judgments anchored on difficulty (Venkatesh's centrality, DeDeo's impasse-experiences)
lose their footing — consistent with the AlephZero essay's predictions about value and aboutness.

---

## 8. New hypotheses generated by this work

These are *new* — they emerged from the measurements above rather than from the literature — and
each is stated so it can be killed by data we know how to get.

**N1. The automation dose–response law — REVISED after testing (§5c).** The original form (per-theorem tactic automation erodes reuse) is *falsified* inside Mathlib: the relation is non-monotonic with a negligible effect size. What survives: automation-heavy *sub-libraries* are measurably less robust (belief 0.786 vs 0.864), and erosion appears strongly between corpora produced by different agents. Erosion is a property of a generating economy, not of a tactic choice. Original statement, retained for the record:

**N1 (original).** Structural erosion of proof networks (rising α, falling
ΔL₁) is monotone in the degree of automation used to produce the proof, *along a single continuum*
that runs: hand-written Coq (α 2.27) → tactic-heavy Lean (2.47) → AI-generated Lean (predicted
higher still). Modularity Q is invariant along that continuum. **Test:** stratify Mathlib proofs by
tactic-automation fraction (`decide`/`norm_num`/`omega`/`aesop` share of the proof term) and check
that α rises monotonically within a single library, holding subject area fixed.

**N2. Modularity is a conserved quantity of mathematics; reuse is not.** Q ≈ 0.71 across proof
assistants, eras, and (2022) across human-written and machine-aided proofs, while α, ΔL₁, and f₂ all
move. Conjecture: modularity is imposed by the *subject matter* (which concepts must be combined),
whereas reuse depth is imposed by the *economy of the producer* (what is cheap to look up vs.
re-derive). **Test — now run and PASSED (§5d):** Q is 0.514 (Gauss) vs 0.509 (human) on the two layers of
sphere packing, while per-opportunity reuse differs 3.4×. The conjecture survives its first real
test; the ETP machine files (Q = 0.145) show it does break when a corpus is generated with no
library intent at all, which bounds the claim.

**N3. Redundancy is a *deliberate* good that verification makes invisible.** The ETP kept 0.13% of
the one-step certificates available to it (Study 4b). The discarded 99.87% was not redundant
*mathematically* — it was redundant only relative to a perfect verifier. **Prediction:** any
formalization project that optimizes for kernel-checked completeness will converge toward a
non-redundant skeleton, and any project that optimizes for human understanding (blueprints, teaching
libraries, Mathlib) will retain redundancy. This makes "how much redundancy did you keep?" a
measurable proxy for *whose* understanding a formalization was built for.

**N4. Deductive depth is prover-relative, and this dissolves a classical intuition.** The ETP's
14-step human-facing chains are depth-1 for Vampire. Depth, difficulty, and therefore "how much a
theorem needs" are not properties of the mathematics but of a (prover, library) pair. **Prediction:**
as provers improve, published proof-network depth distributions for a *fixed* body of results should
compress over time; and mathematicians' judgments of which results are "deep" should decouple from
formal depth faster in areas with strong automation (elementary number theory first — exactly where
we already see the α ≈ 2.9 cluster).

**N5. Repetition-without-reuse — REVISED after the census (§5e).** The phenomenon is real and
sharpest in long proofs (vocabulary ratio 0.287 AI vs 0.495 human for proofs over 80 lines), but it
**fails as a corpus-level classifier** (14 vs 13 corpora, p = 0.51): between-corpus heterogeneity
swamps the authorship signal. Revised claim: repetition-without-reuse is a property of how these
systems handle *long* derivations — they repeat where a human would name a lemma — not a
fingerprint that identifies machine authorship from a corpus in aggregate. The metric that does
separate at every level is automation share (0.250 vs 0.113, p = 10⁻¹⁹⁴), which is a statement
about tactic economy rather than about reuse.

**N6. The library, not the proof, is now the unit of epistemic robustness.** Individual AI proofs
may be structurally impoverished while the accumulated library remains an epistemic fortress
(Study 5: belief ≈ 1 even at ε = 0.3). **Prediction:** as AI-authored content's share of Mathlib
rises, library-level robustness should *decline measurably* — the same measurement repeated on
annual MathlibGraph snapshots is a direct longitudinal test, and one of the few early-warning
indicators available for "AI slop" in formal mathematics.

**N7. Certainty and understanding become independently measurable for the first time.** f₂ (network
certainty) and reuse/redundancy structure (the 2022 correlate of understanding) are decoupled in
machine-verified corpora: the ETP has total certainty and near-zero redundancy. Mathematics has
historically never had a case where the two came apart cleanly, which is why the philosophical
debate could stay stuck on whether formal derivation "captures" a proof. **We now have the
instrument to measure the gap directly**, and the correspondence problem (representation + tracking)
becomes an empirical program rather than a conceptual one.

**N8. Review attention migrates to definitions.** Since proof steps are verified and definitions are
not, human epistemic labor should concentrate on statement/definition nodes. **Test:** classify
GitHub/Zulip review comments in AI-completed projects (Sphere-Packing PR #341 has five months of
review discussion) by the node type they attach to, versus human-era formalization reviews.
Prediction: a large and growing definition-share.

---

## Appendix A. Assets produced

- `~/ai_math_ept/code/` — full toolkit: `ExtractNetwork.lean` (term/decl/term0 extraction),
  `extract_corpus.py` (per-proof pipeline w/ syntax modernization), `proofnet.py`, `belief.py`
  (numba asymmetric-Ising), `run_analysis.py`, `compare_corpora.py`, `study4*.py`, `study5_mathlib.py`.
- `~/ai_math_ept/networks/` — all extracted networks (batch1 classics, coq2022 originals,
  dsv2/kimina/seed/compfiles/alphaproof/aristotle corpora).
- `~/ai_math_ept/results/` — per-study outputs (CSVs, JSONs, curves) + study3_source/REPORT.md.
- `~/ai_math_ept/original_data/` — the recovered 2022 ProofDAGs + CoqAST + ManipulateProofTrees.
- `~/ai_math_ept/projects/` — equational_theories (+complete outcome/Vampire data), pfr, FLT,
  Sphere-Packing-Lean, PrimeNumberTheoremAnd, LeanDojo Benchmark 4, MathlibGraph.

## Appendix B. Known limitations

- Compilation attrition for version-drifted AI corpora (~1/3 of DeepSeek files) — selection is
  toward simpler proofs; matched-pair analyses mitigate.
- ΔL₁ units here differ from the 2022 paper's normalization; comparisons are internal to this
  pipeline (the same-pipeline coq2022 rerun provides the bridge).
- Girvan–Newman replaced by Louvain for large graphs.
- Gauss layer attribution by name-diff (renames would leak human code into the Gauss layer —
  biasing *against* the differences we found).
- The 5 hand-coded human networks from 2022 (Euclid original text, Apollonius, Herstein, Wiles,
  Orlik–Strauch) are not public; era comparison for them uses published Table 1 values only.
