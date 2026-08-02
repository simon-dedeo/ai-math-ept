# Research redirection: from proof shape to construction horizon

## Why redirect

The first phase of this repository successfully recovered the Viteri--DeDeo
pipeline, audited its degree-distribution claims, and produced a controlled
same-theorem comparison.  It also showed why a paper organized around generic
network summaries is unlikely to isolate authorship: theorem identity and graph
representation explain much of the apparent variation, while modeled theorem
belief is close to saturation for both human and AI certificates.

The next phase asks a more fundamental question: **what kind of future is a
proof being built for?**  A proof can be optimized for acceptance of the current
theorem, for the next step in the current proof, for reuse elsewhere in a file,
or for a community that will maintain and extend a library.  These horizons
make different intermediate facts valuable even when the final proposition is
held fixed.

## Candidate principle

The **amortization-horizon principle** says that proof construction differs in
where it pays the cost of abstraction.

- An episode-bound constructor can introduce disposable local facts whenever
  they make the present search easier.
- A library-building constructor benefits from selecting facts whose naming,
  generality, and reuse lower the cost of later reasoning.

This is not proposed as a biological distinction between people and machines.
It predicts a divergence between the objectives under which the available
human- and AI-provenance artifacts were produced.  It also predicts that an AI
trained or scaffolded for library construction can cross the divide.

## Discriminating tests

The following tests are ordered from least to most interpretive.

1. **Matched local decomposition.**  In validated proofs of the same Lean
   statement, compare the number of named intermediate claims.
2. **Intermediate uptake.**  Measure how often a named local claim is explicitly
   referenced downstream.  Report zero-, one-, and multi-uptake claims, with a
   shadowing-aware lexical audit and source-cluster uncertainty.
3. **Elaborated binder use.**  Count occurrences of each local binder in the
   kernel proof term.  This distinguishes a genuinely unused or single-use
   claim from a claim consumed implicitly by `linarith`, `omega`, or another
   context-sensitive tactic.
4. **Library interface.**  Use tactic annotations and elaborated constants to
   compare named-library contact without relying on capitalization regexes.
5. **Amortized savings.**  Estimate the expression work saved when a local
   binding is used repeatedly, rather than reconstructing its value.
6. **Information timing.**  Score human and AI proof scripts with a fixed Lean
   language model.  Test whether surprising material is concentrated before
   abstraction boundaries, analogous to regulation of information flow in
   conversation, and whether names reduce downstream surprisal.
7. **Corpus accumulation.**  Separate episode-generated corpora from
   library-building projects and test whether later citation, API survival, and
   refactoring behavior follow the production horizon more closely than the
   human/AI label.

## Claims deliberately demoted

- Near-equality under the Viteri--DeDeo belief model is a model diagnostic, not
  evidence that readers understand the two populations equally.
- A heavy-tailed reuse distribution is a property of a declared graph boundary,
  not a representation-free cognitive law.
- The machine-generated Equational Theories files are a useful extreme case,
  not by themselves evidence that all machine mathematics fails to accumulate.
- Proof length is not proof quality, and local claim count alone is not
  modularity.  Uptake and future use are required.

## Falsification conditions

The candidate principle should be abandoned or sharply narrowed if (i) the
uptake contrast vanishes under elaborated binder-use analysis, (ii) it is
explained by a small number of tactic families or source groups, (iii) AI
library-building projects show the same horizon as episode-bound generation,
or (iv) refactoring toward reusable intermediate claims does not improve either
future proof cost or human comprehension.
