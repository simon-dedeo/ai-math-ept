# The horizon of a proof

## Core distinction

A Lean proof has at least three products:

1. a **certificate**, consumed by the kernel for the theorem at hand;
2. an **episode structure**, consumed by the constructor and a reader while
   navigating the current proof; and
3. an **interface**, consumed by future proofs through exported declarations,
   stable names, and explanatory boundaries.

Compilation evaluates the first product. Most proof-generation benchmarks end
there. Human formalization is often embedded in a longer activity: maintenance,
explanation, and construction of a library. Calling every intermediate fact a
"lemma" hides these different consumers.

## Amortization-horizon principle

An abstraction is worth buying when its discounted future savings exceed its
construction and interface costs. For an abstraction `z`, write

```text
V_gamma(z) = sum_{u in uses(z)} gamma^distance(z,u) savings(u)
             - construction_cost(z) - interface_cost(z).
```

The relevant `uses` may be occurrences in a kernel term, later steps in the
same source proof, later theorems in a repository, or retrieval by another
person. The horizon parameter `gamma` is an objective property, not a species
label. A compile-first generator can rationally create disposable local claims
that improve current search while investing nothing in names or reusable APIs.
An AI rewarded for refactoring and downstream reuse should behave differently.

## Proofs as multiscale memory

The three products correspond to different memory scales:

- A proof-term `let` is a sharing node. Repeated use turns an expression tree
  into a DAG and can avoid duplication.
- A source-level `have` is addressable working memory. It can expose search
  state even when the elaborated binder is dead or used once.
- An exported theorem is persistent memory. Its cost is paid once while its
  statement, name, and proof can serve a stream of later tasks.

This yields a more precise empirical vocabulary. **Dead binders** diagnose
transient state. **Explicit uptake** diagnoses visible hand-offs in the proof
script. **Term use** diagnoses kernel sharing, including implicit consumption
by tactics. **Cross-declaration citation** diagnoses library accumulation.
None is a general-purpose measure of "modularity."

## An amortized proof-complexity object

Ordinary proof complexity asks for the shortest certificate of one formula.
Library construction suggests a sequence-level object. For targets
`phi_1, ..., phi_T`, define informally

```text
APC_lambda(phi_1:T) = min_{library L, proofs P_1:T}
    lambda * size(L) + sum_t size(P_t | L),
```

subject to every library declaration and proof checking in the base system.
An online version charges when declarations are introduced and measures regret
against the best hindsight library. This is closely related to grammar-based
compression and reusable subroutines: a library is valuable when shared
structure pays back its interface cost over a theorem stream. It also clarifies
why a one-theorem benchmark cannot measure library-building competence.

The analogy with extension variables and circuit sharing is deliberately
limited. A Lean local binder can name a repeated subterm, but dependent types,
tactics, reduction, and elaboration mean that source claims are not literally
Extended Frege extension axioms. The defensible connection is the change from a
tree accounting to a DAG or reusable-interface accounting.

## Empirical predictions

Holding the target statement fixed, a shorter construction horizon predicts:

- more local state that is absent from the final proof term;
- more one-step or lexically unreferenced claims;
- generic names, because names need only be locally distinct;
- weaker pressure to expose stable declarations for later retrieval; and
- large improvements when a separate refactoring/library objective is added.

A longer horizon predicts fewer but longer-lived visible invariants, greater
investment in meaningful names, and greater cross-proof reuse. It does **not**
predict that every human proof is concise or that every AI proof is disposable.

## What would disconfirm the account

The horizon account should be narrowed or rejected if the same differences
remain after systems are equated for objective and workflow; if dead-binder and
visible-uptake contrasts vanish under scope-correct elaboration; if meaningful
naming does not improve human comprehension or maintenance; or if agents given
downstream-library rewards do not learn to construct reusable interfaces.
