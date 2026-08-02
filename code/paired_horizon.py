"""Same-theorem tests of the proof-construction horizon.

This analysis uses every NuminaMath-LEAN artifact for which both the human
annotation and the prover output are marked valid.  Unlike the earlier source
analysis, it does not require a regex-detected library premise, so the inclusion
rule is independent of the outcome metrics.

The primary source-level object is a named ``have`` claim.  Lean parser ranges
exclude the complete tactic that constructs each claim; we then count later
*explicit* references to its name, stopping before a later claim that shadows
the same name.  This is intentionally not called semantic use: context-sensitive
tactics can consume a hypothesis without naming it.  A separate elaborated-term
analysis is needed for that stronger claim.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import optimize, stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from census import proof_bodies, strip_noncode  # noqa: E402


LEAN_IDENT = r"(?:«[^»\n]+»|[^\W\d][\w']*|_[\w']+)"
HAVE_START = re.compile(rf"\bhave\s+({LEAN_IDENT})(?=\s|:|:=)", re.UNICODE)
ANON_HAVE = re.compile(r"\bhave(?:\s+_)?\s*(?=:)")
TOKEN = re.compile(LEAN_IDENT, re.UNICODE)
TACTIC_HEAD = re.compile(r"(?:[·.\-+]\s*)?([A-Za-z_][A-Za-z0-9_?']*)")
PLACEHOLDER_NAME = re.compile(
    r"(?:h|h[a-z]?|this|step|eq|ineq|hx|hy|hz|ha|hb|hc|aux|claim)\d*", re.I
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def huggingface_revisions(root: Path) -> list[str]:
    metadata = (
        root / "census" / "numinamath-proof-artifacts" / ".cache"
        / "huggingface" / "download"
    ).glob("**/*.metadata")
    revisions = {
        lines[0]
        for path in metadata
        for lines in [path.read_text().splitlines()]
        if lines
    }
    return sorted(revisions)


def proof_body(source: str) -> str:
    """Return the final theorem body's comment/string-free source.

    Numina artifacts may include helper declarations before the target theorem.
    Restricting to the final declaration keeps the paired comparison at the
    same target rather than silently pooling artifact-level helper libraries.
    """
    clean = strip_noncode(source if isinstance(source, str) else "")
    bodies = list(proof_bodies(clean, strip=False))
    return bodies[-1][2] if bodies else clean


def target_value_fragment(body: str) -> tuple[str, int] | None:
    """Return the target proof value and its character offset in ``body``.

    ``proof_body`` deliberately retains the declaration suffix so earlier
    analyses can inspect theorem parameters.  For parsing local tactics, scan
    to the first top-level ``:=``; binders can contain their own defaults, but
    those separators occur inside balanced delimiters.
    """
    closing = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []
    position = 0
    while position + 1 < len(body):
        char = body[position]
        if char in closing:
            stack.append(closing[char])
        elif stack and char == stack[-1]:
            stack.pop()
        elif not stack and body.startswith(":=", position):
            start = position + 2
            while start < len(body) and body[start].isspace():
                start += 1
            return body[start:], start
        position += 1
    return None


def pretarget_audit(source: str) -> dict[str, Any]:
    """Describe declarations supplied before the final target theorem.

    These declarations are tempting evidence of persistent interface building,
    but many Numina artifacts copy the same problem scaffolding into both the
    human and prover tracks.  Retaining a normalized signature lets the paired
    analysis distinguish shared input from side-specific helper invention.
    """
    declarations = list(proof_bodies(source if isinstance(source, str) else ""))
    helpers = declarations[:-1]
    target = declarations[-1][2] if declarations else ""
    names = [name for name, _kind, _body in helpers]
    used = [
        name for name in names
        if re.search(rf"(?<![\w'.]){re.escape(name)}(?![\w'.])", target)
    ]
    signature = [
        (name, kind, " ".join(body.split()))
        for name, kind, body in helpers
    ]
    return {
        "count": len(helpers),
        "used_count": len(used),
        "names": names,
        "signature": signature,
    }


def serialized_target_signature(value: Any) -> tuple[str, str, str] | None:
    """Normalize the final declaration recorded by the dataset's elaborator.

    The structured declaration record avoids guessing where a term-style Lean
    proof begins. Comments are removed because they can occur inside the
    pretty-printed signature without changing the proposition.
    """
    if not isinstance(value, (list, np.ndarray)) or len(value) == 0:
        return None
    declaration = value[-1]
    if not isinstance(declaration, dict):
        return None
    signature = declaration.get("signature", {})
    if not isinstance(signature, dict):
        return None
    return (
        str(declaration.get("kind", "")),
        str(declaration.get("full_name", "")),
        " ".join(strip_noncode(str(signature.get("pp", ""))).split()),
    )


def serialized_target_value(value: Any) -> str | None:
    """Return the dataset elaborator's final proof value, without comments."""
    if not isinstance(value, (list, np.ndarray)) or len(value) == 0:
        return None
    declaration = value[-1]
    if not isinstance(declaration, dict):
        return None
    proof_value = declaration.get("value", {})
    if not isinstance(proof_value, dict) or "pp" not in proof_value:
        return None
    return " ".join(strip_noncode(str(proof_value["pp"])).split())


def named_have_declarations(body: str) -> list[dict[str, Any]]:
    """Locate named ``have`` headers, including binder-bearing local lemmas.

    The former regular expression required ``:`` or ``:=`` immediately after
    the name and therefore omitted declarations such as ``have f (x : α) :``.
    Here a small balanced-delimiter scan finds the first top-level type/value
    separator and records how many explicit binder groups precede it.
    """
    openings = {"(": ")", "[": "]", "{": "}"}
    declarations: list[dict[str, Any]] = []
    for match in HAVE_START.finditer(body):
        # A lone underscore is Lean's inaccessible placeholder, not a name a
        # later source token can retrieve.  Treat `have _ : ...` with the
        # anonymous-have census rather than manufacturing lexical references
        # from unrelated wildcard underscores.
        if match.group(1) == "_":
            continue
        stack: list[str] = []
        binder_groups = 0
        top_level_header: list[str] = []
        position = match.end()
        end: int | None = None
        while position < len(body):
            char = body[position]
            if char in openings:
                if not stack:
                    binder_groups += 1
                stack.append(openings[char])
            elif stack and char == stack[-1]:
                stack.pop()
            elif not stack and body.startswith(":=", position):
                end = position + 2
                break
            elif not stack and char == ":":
                end = position + 1
                break
            elif not stack and char == ";":
                break
            elif not stack:
                top_level_header.append(char)
            position += 1
        if end is not None:
            # Lean also permits unbracketed binders, as in `have h x := ...`.
            binder_groups += len(TOKEN.findall("".join(top_level_header)))
            universal_type = bool(
                re.match(r"\s*\(*\s*(?:∀|forall\b)", body[end:])
            )
            declarations.append({
                "name": match.group(1),
                "start": match.start(),
                "end": end,
                "name_start": match.start(1),
                "name_end": match.end(1),
                "binder_groups": binder_groups,
                "universal_type": universal_type,
            })
    return declarations


def parser_have_ranges(
    sources: list[str], root: Path, environment: str = "mathlib4"
) -> tuple[list[list[tuple[int, int, int]] | None], dict[str, Any]]:
    """Get exact tactic-`have` construction and scope ranges from Lean.

    Lean reports UTF-8 byte positions, while Python regular expressions use
    Unicode-codepoint offsets.  Convert positions here so every downstream
    window is expressed in the same coordinate system as ``source``.
    ``None`` denotes a body that the current Mathlib parser could not read.
    """
    helper = root / "code" / "ExtractHaveRanges.lean"
    fragments_with_offsets = [target_value_fragment(source) for source in sources]
    fragments = [item[0] if item is not None else "" for item in fragments_with_offsets]
    completed = subprocess.run(
        ["lake", "env", "lean", "--run", str(helper)],
        cwd=root / environment,
        input="\0".join(fragments),
        text=True,
        capture_output=True,
        check=True,
    )
    lines = completed.stdout.splitlines()
    if len(lines) != len(sources):
        raise RuntimeError(
            f"Lean range helper returned {len(lines)} lines for {len(sources)} sources"
        )
    output: list[list[tuple[int, int, int]] | None] = []
    for source, fragment_info, line in zip(sources, fragments_with_offsets, lines):
        if fragment_info is None or line.startswith("ERROR"):
            output.append(None)
            continue
        fragment, character_offset = fragment_info
        byte_ranges = [] if not line else [
            tuple(int(value) for value in item.split(":"))
            for item in line.split(",")
        ]
        encoded = fragment.encode("utf-8")
        output.append([
            (
                character_offset + len(encoded[:start].decode("utf-8")),
                character_offset + len(encoded[:tail].decode("utf-8")),
                character_offset + len(encoded[:scope_tail].decode("utf-8")),
            )
            for start, tail, scope_tail in byte_ranges
        ])
    return output, {
        "terms": len(sources),
        "parsed": sum(ranges is not None for ranges in output),
        "failed": sum(ranges is None for ranges in output),
        "helper": "code/ExtractHaveRanges.lean",
        "environment": environment,
        "coordinate_conversion": "Lean UTF-8 byte offsets to Python Unicode offsets",
        "scope_rule": "tail of nearest enclosing tacticSeq parser node",
    }


def named_have_claims(
    source: str,
    construction_ranges: list[tuple[int, int] | tuple[int, int, int]] | None = None,
    require_parser_match: bool = False,
) -> list[dict[str, Any]]:
    """Extract named haves and count later explicit uptake.

    Counting begins after the complete construction range supplied by Lean's
    parser.  The window ends at the nearest enclosing tactic sequence's tail,
    or earlier at a same-name redeclaration.  The latter is conservative in
    constructs whose exact binder scope is smaller than the tactic sequence.
    """
    body = proof_body(source)
    matches = named_have_declarations(body)
    for source_claim_index, match in enumerate(matches):
        match["source_claim_index"] = source_claim_index
    all_matches = matches
    counts = Counter(match["name"] for match in all_matches)
    range_by_start = {
        item[0]: (item[1], item[2] if len(item) == 3 else len(body))
        for item in (construction_ranges or [])
    }
    for match in matches:
        match["parser_range_matched"] = match["start"] in range_by_start
        construction_end, scope_end = range_by_start.get(
            match["start"], (match["end"], len(body))
        )
        match["construction_end"] = construction_end
        match["scope_end"] = scope_end
    if require_parser_match:
        matches = [match for match in matches if match["parser_range_matched"]]

    claims: list[dict[str, Any]] = []
    for i, match in enumerate(matches):
        name = match["name"]
        construction_end = int(match["construction_end"])
        scope_end = int(match["scope_end"])
        unscoped_next_same = next((
            later["start"]
            for later in all_matches[int(match["source_claim_index"]) + 1:]
            if later["name"] == name and later["start"] >= construction_end
        ), len(body))
        next_same = next((
            later["start"]
            for later in all_matches[int(match["source_claim_index"]) + 1:]
            if (
                later["name"] == name
                and construction_end <= later["start"] < scope_end
            )
        ), scope_end)
        token_matches = [
            token for token in TOKEN.finditer(body, construction_end, next_same)
            if token.group(0) == name
        ]
        unscoped_token_matches = [
            token
            for token in TOKEN.finditer(body, construction_end, unscoped_next_same)
            if token.group(0) == name
        ]
        use_positions = [token.start() for token in token_matches]
        first_delay = (
            len(TOKEN.findall(body[construction_end : use_positions[0]]))
            if use_positions else None
        )
        last_delay = (
            len(TOKEN.findall(body[construction_end : use_positions[-1]]))
            if use_positions else None
        )
        claim_span = (
            sum(
                construction_end < later["start"] < use_positions[-1]
                for later in matches
            )
            if use_positions else None
        )
        later_claims_available = sum(
            construction_end < later["start"] < next_same
            for later in matches
        )
        claims.append(
            {
                "claim_index": int(match["source_claim_index"]),
                "name": name,
                "parser_range_matched": bool(match["parser_range_matched"]),
                "construction_end": construction_end,
                "scope_end": scope_end,
                "binder_groups": int(match["binder_groups"]),
                "parametric_claim": bool(match["binder_groups"]),
                "universal_claim": bool(match["universal_type"]),
                "generalized_claim": bool(
                    match["binder_groups"] or match["universal_type"]
                ),
                "explicit_uses": len(use_positions),
                "unscoped_explicit_uses": len(unscoped_token_matches),
                "scope_excluded_reference_tokens": (
                    len(unscoped_token_matches) - len(token_matches)
                ),
                "scope_clipped": scope_end < len(body),
                "first_use_delay_tokens": first_delay,
                "last_use_delay_tokens": last_delay,
                "intervening_claims_to_last_use": claim_span,
                "later_claims_available": later_claims_available,
                "fraction_available_claims_to_last_use": (
                    claim_span / later_claims_available
                    if use_positions and later_claims_available else None
                ),
                "redeclared_name": counts[name] > 1,
                "placeholder_name": bool(
                    PLACEHOLDER_NAME.fullmatch(unicodedata.normalize("NFKC", name))
                ),
            }
        )
    return claims


def tactic_annotation_metrics(value: Any) -> dict[str, Any]:
    """Summarize the dataset's elaborator-generated tactic annotations.

    Nested tactic annotations overlap, so event and reference totals are only
    descriptive.  The union of ``used_constants`` is invariant to duplicate
    nesting and is the primary annotation-based interface measure.
    """
    if not isinstance(value, (list, np.ndarray)):
        return {
            "tactic_events": 0,
            "tactic_types": 0,
            "used_constants": 0,
            "constant_annotations": 0,
        }
    heads: list[str] = []
    constants: list[str] = []
    for event in value:
        if not isinstance(event, dict):
            continue
        match = TACTIC_HEAD.match(str(event.get("tactic", "")).strip())
        if match:
            heads.append(match.group(1))
        used = event.get("used_constants", [])
        if isinstance(used, (list, np.ndarray)):
            constants.extend(str(item) for item in used)
    out: dict[str, Any] = {
        "tactic_events": len(value),
        "tactic_types": len(set(heads)),
        "used_constants": len(set(constants)),
        "constant_annotations": len(constants),
    }
    for head in (
        "aesop", "apply", "constructor", "exact", "linarith", "nlinarith",
        "norm_num", "omega", "ring", "ring_nf", "rw", "simp", "simpa",
    ):
        out[f"event_{head}"] = heads.count(head)
    return out


def side_metrics(
    source: str,
    tactics: Any,
    construction_ranges: list[tuple[int, int] | tuple[int, int, int]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    body = proof_body(source)
    regex_claim_count = len(named_have_declarations(body))
    claims = named_have_claims(
        source, construction_ranges, require_parser_match=True
    )
    uses = np.asarray([claim["explicit_uses"] for claim in claims], dtype=int)
    spans = np.asarray([
        claim["intervening_claims_to_last_use"]
        for claim in claims if claim["intervening_claims_to_last_use"] is not None
    ], dtype=int)
    last_delays = np.asarray([
        claim["last_use_delay_tokens"]
        for claim in claims if claim["last_use_delay_tokens"] is not None
    ], dtype=int)
    metrics: dict[str, Any] = {
        "tokens": len(re.findall(r"\S+", body)),
        "chars": len(body),
        "named_haves": len(claims),
        "regex_named_haves": regex_claim_count,
        "parser_unmatched_named_haves": regex_claim_count - len(claims),
        "anonymous_haves": len(ANON_HAVE.findall(body)),
        "explicit_uses": int(uses.sum()) if len(uses) else 0,
        "unscoped_explicit_uses": sum(
            claim["unscoped_explicit_uses"] for claim in claims
        ),
        "scope_excluded_references": sum(
            claim["scope_excluded_reference_tokens"] for claim in claims
        ),
        "scope_clipped_haves": sum(claim["scope_clipped"] for claim in claims),
        "zero_uptake_haves": int((uses == 0).sum()) if len(uses) else 0,
        "one_uptake_haves": int((uses == 1).sum()) if len(uses) else 0,
        "multi_uptake_haves": int((uses > 1).sum()) if len(uses) else 0,
        "adopted_haves": int((uses > 0).sum()) if len(uses) else 0,
        "reuse_excess": int(np.maximum(uses - 1, 0).sum()) if len(uses) else 0,
        "long_horizon_haves": int((spans > 0).sum()) if len(spans) else 0,
        "total_claim_span": int(spans.sum()) if len(spans) else 0,
        "max_claim_span": int(spans.max()) if len(spans) else 0,
        "total_last_use_delay_tokens": int(last_delays.sum()) if len(last_delays) else 0,
        "placeholder_haves": sum(claim["placeholder_name"] for claim in claims),
        "descriptively_named_haves": sum(
            not claim["placeholder_name"] for claim in claims
        ),
        "redeclared_haves": sum(claim["redeclared_name"] for claim in claims),
        "parametric_haves": sum(claim["parametric_claim"] for claim in claims),
        "universal_haves": sum(claim["universal_claim"] for claim in claims),
        "generalized_haves": sum(claim["generalized_claim"] for claim in claims),
        "total_binder_groups": sum(claim["binder_groups"] for claim in claims),
    }
    for tactic in ("native_decide", "decide", "norm_num", "aesop"):
        metrics[f"source_tactic_{tactic}"] = int(bool(
            re.search(rf"(?<![\w'.]){re.escape(tactic)}(?![\w'.])", body)
        ))
    metrics.update(tactic_annotation_metrics(tactics))
    return metrics, claims


def _cluster_ratio_bootstrap(
    frame: pd.DataFrame,
    numerator: str,
    denominator: str,
    n_boot: int,
    rng: np.random.Generator,
) -> list[float]:
    grouped = frame.groupby("source")[[numerator, denominator]].sum()
    values = grouped.to_numpy(float)
    draws = rng.integers(0, len(values), size=(n_boot, len(values)))
    selected = values[draws]
    num = selected[:, :, 0].sum(axis=1)
    den = selected[:, :, 1].sum(axis=1)
    return [float(x) for x in num / np.maximum(den, 1.0)]


def _cluster_median_bootstrap(
    frame: pd.DataFrame,
    values: np.ndarray,
    n_boot: int,
    rng: np.random.Generator,
) -> list[float]:
    grouped = [values[index] for index in frame.groupby("source").indices.values()]
    draws: list[float] = []
    for _ in range(n_boot):
        selected = rng.integers(0, len(grouped), len(grouped))
        draws.append(float(np.median(np.concatenate([grouped[i] for i in selected]))))
    return draws


def _ci(values: Iterable[float]) -> list[float]:
    return [float(x) for x in np.percentile(list(values), [2.5, 97.5])]


def paired_metric(
    frame: pd.DataFrame,
    metric: str,
    n_boot: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    human = frame[f"h_{metric}"].to_numpy(float)
    ai = frame[f"a_{metric}"].to_numpy(float)
    difference = ai - human
    try:
        pvalue = float(stats.wilcoxon(human, ai).pvalue)
    except ValueError:
        pvalue = 1.0
    return {
        "n": len(frame),
        "human_median": float(np.median(human)),
        "ai_median": float(np.median(ai)),
        "median_paired_difference": float(np.median(difference)),
        "probability_ai_greater": float(np.mean(difference > 0)),
        "cluster_ci": _ci(_cluster_median_bootstrap(frame, difference, n_boot, rng)),
        "wilcoxon_p": pvalue,
    }


def claim_rate(
    frame: pd.DataFrame,
    side: str,
    numerator: str,
    n_boot: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    num = f"{side}_{numerator}"
    den = f"{side}_named_haves"
    estimate = float(frame[num].sum() / max(frame[den].sum(), 1))
    return {
        "numerator": int(frame[num].sum()),
        "denominator": int(frame[den].sum()),
        "estimate": estimate,
        "source_cluster_ci": _ci(_cluster_ratio_bootstrap(frame, num, den, n_boot, rng)),
    }


def claim_rate_difference(
    frame: pd.DataFrame,
    numerator: str,
    n_boot: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    columns = [
        f"h_{numerator}", "h_named_haves",
        f"a_{numerator}", "a_named_haves",
    ]
    grouped = frame.groupby("source")[columns].sum().to_numpy(float)
    draws = rng.integers(0, len(grouped), size=(n_boot, len(grouped)))
    sampled = grouped[draws].sum(axis=1)
    differences = (
        sampled[:, 2] / np.maximum(sampled[:, 3], 1)
        - sampled[:, 0] / np.maximum(sampled[:, 1], 1)
    )
    h_rate = float(frame[columns[0]].sum() / max(frame[columns[1]].sum(), 1))
    a_rate = float(frame[columns[2]].sum() / max(frame[columns[3]].sum(), 1))
    positive = frame[frame[columns[1]].gt(0) & frame[columns[3]].gt(0)]
    h_per_proof = positive[columns[0]] / positive[columns[1]]
    a_per_proof = positive[columns[2]] / positive[columns[3]]
    try:
        pvalue = float(stats.wilcoxon(h_per_proof, a_per_proof).pvalue)
    except ValueError:
        pvalue = 1.0
    return {
        "human": h_rate,
        "ai": a_rate,
        "ai_minus_human": a_rate - h_rate,
        "source_cluster_ci": _ci(differences),
        "paired_wilcoxon_p": pvalue,
    }


def token_supply_difference(
    frame: pd.DataFrame,
    numerator: str,
    n_boot: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Compare pooled claim supply per 100 proof-body tokens.

    Source-cluster resampling preserves the paired corpus while keeping the
    denominator distinct from the per-claim selectivity estimands above.
    """
    columns = [
        f"h_{numerator}", "h_tokens",
        f"a_{numerator}", "a_tokens",
    ]
    grouped = frame.groupby("source")[columns].sum().to_numpy(float)
    draws = rng.integers(0, len(grouped), size=(n_boot, len(grouped)))
    sampled = grouped[draws].sum(axis=1)
    differences = 100 * (
        sampled[:, 2] / np.maximum(sampled[:, 3], 1)
        - sampled[:, 0] / np.maximum(sampled[:, 1], 1)
    )
    human = float(100 * frame[columns[0]].sum() / max(frame[columns[1]].sum(), 1))
    ai = float(100 * frame[columns[2]].sum() / max(frame[columns[3]].sum(), 1))
    return {
        "unit": "claims per 100 proof-body whitespace tokens",
        "human_numerator": int(frame[columns[0]].sum()),
        "human_denominator": int(frame[columns[1]].sum()),
        "ai_numerator": int(frame[columns[2]].sum()),
        "ai_denominator": int(frame[columns[3]].sum()),
        "human": human,
        "ai": ai,
        "ai_minus_human": ai - human,
        "source_cluster_ci": _ci(differences),
    }


def claim_count_sensitivity(
    frame: pd.DataFrame,
    n_boot: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    positive = frame[frame.h_named_haves.gt(0) & frame.a_named_haves.gt(0)]
    subsets = {
        "exact_equal_positive": positive[
            positive.h_named_haves.eq(positive.a_named_haves)
        ],
        "within_one_positive": positive[
            positive.h_named_haves.sub(positive.a_named_haves).abs().le(1)
        ],
    }
    return {
        label: {
            "pairs": int(len(subset)),
            "source_groups": int(subset.source.nunique()),
            "explicit_uses_per_claim": claim_rate_difference(
                subset, "explicit_uses", n_boot, rng
            ),
            "zero_uptake_share": claim_rate_difference(
                subset, "zero_uptake_haves", n_boot, rng
            ),
            "generalized_claim_share": claim_rate_difference(
                subset, "generalized_haves", n_boot, rng
            ),
        }
        for label, subset in subsets.items()
    }


def length_matched_sensitivity(
    frame: pd.DataFrame,
    n_boot: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    token_min = frame[["h_tokens", "a_tokens"]].min(axis=1).clip(lower=1)
    token_max = frame[["h_tokens", "a_tokens"]].max(axis=1)
    subsets = {
        "within_ten_percent": frame[token_max.div(token_min).le(1.10)],
        "within_twenty_tokens": frame[frame.a_tokens.sub(frame.h_tokens).abs().le(20)],
    }
    return {
        label: {
            "pairs": int(len(subset)),
            "source_groups": int(subset.source.nunique()),
            **{
                metric: claim_rate_difference(subset, numerator, n_boot, rng)
                for metric, numerator in (
                    ("explicit_uses_per_claim", "explicit_uses"),
                    ("zero_uptake_share", "zero_uptake_haves"),
                    ("long_horizon_share", "long_horizon_haves"),
                    ("generalized_claim_share", "generalized_haves"),
                )
            },
        }
        for label, subset in subsets.items()
    }


def nonredeclared_name_sensitivity(
    claims: pd.DataFrame,
    n_boot: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Recompute claim rates where a name occurs only once in its proof.

    This removes every claim for which the conservative lexical stopping rule
    could truncate a later reference at a same-name declaration.
    """
    subset = claims[~claims.redeclared_name.astype(bool)].copy()
    subset["zero_uptake"] = subset.explicit_uses.eq(0).astype(int)
    subset["multi_uptake"] = subset.explicit_uses.gt(1).astype(int)
    subset["long_horizon"] = subset.intervening_claims_to_last_use.fillna(0).gt(0).astype(int)
    sources = sorted(claims.source.unique())
    output: dict[str, Any] = {
        "rule": "retain only claim names occurring exactly once in that proof",
    }
    for label, numerator in (
        ("explicit_uses_per_claim", "explicit_uses"),
        ("zero_uptake_share", "zero_uptake"),
        ("multi_uptake_share", "multi_uptake"),
        ("long_horizon_share", "long_horizon"),
    ):
        grouped = (
            subset.groupby(["source", "side"])[numerator]
            .agg(["sum", "size"])
            .reindex(pd.MultiIndex.from_product([sources, ["h", "a"]]), fill_value=0)
        )
        values = np.asarray([
            [
                grouped.loc[(source, "h"), "sum"],
                grouped.loc[(source, "h"), "size"],
                grouped.loc[(source, "a"), "sum"],
                grouped.loc[(source, "a"), "size"],
            ]
            for source in sources
        ], dtype=float)
        total = values.sum(axis=0)
        human = float(total[0] / max(total[1], 1))
        ai = float(total[2] / max(total[3], 1))
        draws = rng.integers(0, len(values), size=(n_boot, len(values)))
        sampled = values[draws].sum(axis=1)
        differences = (
            sampled[:, 2] / np.maximum(sampled[:, 3], 1)
            - sampled[:, 0] / np.maximum(sampled[:, 1], 1)
        )
        output[label] = {
            "human": human,
            "ai": ai,
            "ai_minus_human": ai - human,
            "source_cluster_ci": _ci(differences),
            "human_claims": int(total[1]),
            "ai_claims": int(total[3]),
        }
    return output


def uptake_reach_decomposition(
    claims: pd.DataFrame,
    n_boot: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Separate whether a claim is adopted from how long an adopted claim lives.

    A later-claim count is partly endogenous to decomposition density.  We
    therefore report both token distance and the fraction of available later
    claim boundaries crossed, as well as the coarse probability of crossing
    any boundary among claims that were used and actually had one available.
    Every interval resamples source groups, preserving the corpus-level unit
    used by the primary claim-rate analysis.
    """
    work = claims.copy()
    work["adopted"] = work.explicit_uses.gt(0).astype(float)
    work["last_delay_or_zero"] = work.last_use_delay_tokens.fillna(0).astype(float)
    work["crossed_boundary"] = work.intervening_claims_to_last_use.fillna(0).gt(0).astype(float)
    work["eligible_crossing"] = (
        work.explicit_uses.gt(0) & work.later_claims_available.gt(0)
    )

    specifications = {
        "adoption_probability": (work.index == work.index, "adopted"),
        "last_use_token_distance_all_claims": (work.index == work.index, "last_delay_or_zero"),
        "explicit_use_count_given_adoption": (work.adopted.eq(1), "explicit_uses"),
        "last_use_token_distance_given_adoption": (work.adopted.eq(1), "last_use_delay_tokens"),
        "crosses_any_later_boundary_given_adoption_and_opportunity": (
            work.eligible_crossing, "crossed_boundary"
        ),
        "fraction_available_boundaries_crossed_given_adoption": (
            work.fraction_available_claims_to_last_use.notna(),
            "fraction_available_claims_to_last_use",
        ),
    }
    sources = sorted(work.source.unique())
    output: dict[str, Any] = {
        "interpretation": (
            "adoption is the extensive margin; remaining measures condition on explicit uptake "
            "and distinguish token distance from claim-boundary opportunity"
        )
    }
    for label, (mask, value_column) in specifications.items():
        selected = work.loc[mask, ["source", "side", value_column]].copy()
        grouped = (
            selected.groupby(["source", "side"])[value_column]
            .agg(["sum", "size"])
            .reindex(pd.MultiIndex.from_product([sources, ["h", "a"]]), fill_value=0)
        )
        values = np.asarray([
            [
                grouped.loc[(source, "h"), "sum"],
                grouped.loc[(source, "h"), "size"],
                grouped.loc[(source, "a"), "sum"],
                grouped.loc[(source, "a"), "size"],
            ]
            for source in sources
        ], dtype=float)
        total = values.sum(axis=0)
        human = float(total[0] / max(total[1], 1))
        ai = float(total[2] / max(total[3], 1))
        draws = rng.integers(0, len(values), size=(n_boot, len(values)))
        sampled = values[draws].sum(axis=1)
        differences = (
            sampled[:, 2] / np.maximum(sampled[:, 3], 1)
            - sampled[:, 0] / np.maximum(sampled[:, 1], 1)
        )
        output[label] = {
            "human": human,
            "ai": ai,
            "ai_minus_human": ai - human,
            "source_cluster_ci": _ci(differences),
            "human_claims": int(total[1]),
            "ai_claims": int(total[3]),
        }
    return output


def name_lexicon(frame: pd.DataFrame, side: str) -> dict[str, Any]:
    """Descriptive diversity of source-level claim names.

    Entropy is computed on pooled name tokens and is therefore a corpus
    descriptor, not an independent-observation significance test.
    """
    names = [unicodedata.normalize("NFKC", str(x))
             for x in frame.loc[frame.side.eq(side), "name"]]
    counts = Counter(names)
    total = max(sum(counts.values()), 1)
    probabilities = np.asarray(list(counts.values()), dtype=float) / total
    entropy_bits = float(-(probabilities * np.log2(probabilities)).sum())
    return {
        "tokens": len(names),
        "types": len(counts),
        "shannon_entropy_bits": entropy_bits,
        "effective_vocabulary": float(2 ** entropy_bits),
        "mean_name_length": float(np.mean([len(x) for x in names])) if names else 0.0,
        "share_length_at_least_4": float(np.mean([len(x) >= 4 for x in names])) if names else 0.0,
        "share_with_underscore": float(np.mean(["_" in x for x in names])) if names else 0.0,
    }


def flagged_claim_profile(
    frame: pd.DataFrame, side: str, flag: str
) -> dict[str, Any]:
    """Describe the fate of claims selected by a source-level flag.

    These are pooled conditional descriptors, not causal or paired estimates:
    the human and AI tracks usually introduce them in different theorems.
    """
    selected = frame[frame.side.eq(side) & frame[flag].astype(bool)].copy()
    if selected.empty:
        return {"claims": 0}
    uses = selected.explicit_uses.astype(float)
    long_reach = selected.intervening_claims_to_last_use.fillna(0).gt(0)
    return {
        "claims": int(len(selected)),
        "source_groups": int(selected.source.nunique()),
        "mean_binder_groups": float(selected.binder_groups.mean()),
        "explicit_uses_per_claim": float(uses.mean()),
        "zero_uptake_share": float(uses.eq(0).mean()),
        "multi_uptake_share": float(uses.gt(1).mean()),
        "long_horizon_share": float(long_reach.mean()),
        "placeholder_name_share": float(selected.placeholder_name.mean()),
        "scope_note": "pooled conditional descriptor; tracks need not contain selected claims in the same theorem",
    }


def within_proof_feature_associations(
    frame: pd.DataFrame,
    n_boot: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Ask whether proposed interface features have a local functional correlate.

    For each proof that contains both flagged and unflagged claims, compute the
    difference in mean fate between those two sets.  This holds the theorem,
    proof, and provenance track fixed.  The result is descriptive rather than
    causal: constructors can choose a general statement precisely when they
    expect to use it.  Source-cluster resampling preserves the primary
    uncertainty convention used elsewhere in the report.
    """
    work = frame.copy()
    work["adopted"] = work.explicit_uses.gt(0).astype(float)
    work["multi_uptake"] = work.explicit_uses.gt(1).astype(float)
    work["long_horizon"] = (
        work.intervening_claims_to_last_use.fillna(0).gt(0).astype(float)
    )
    work["outside_placeholder"] = (~work.placeholder_name.astype(bool))
    for feature in ("parametric_claim", "universal_claim", "generalized_claim"):
        if feature not in work:
            work[feature] = False
    outcomes = (
        "adopted", "multi_uptake", "long_horizon", "explicit_uses"
    )
    output: dict[str, Any] = {
        "estimand": (
            "mean flagged-minus-unflagged claim fate within proofs containing both; "
            "descriptive association, not a causal feature effect"
        )
    }
    sources = sorted(work.source.unique())
    for feature in (
        "parametric_claim", "universal_claim", "generalized_claim",
        "outside_placeholder",
    ):
        output[feature] = {}
        contrasts_by_side: dict[str, pd.DataFrame] = {}
        for side, label in (("h", "human"), ("a", "ai")):
            selected = work[work.side.eq(side)]
            rows: list[dict[str, Any]] = []
            for (pair, source), group in selected.groupby(["pair", "source"]):
                flag = group[feature].astype(bool)
                if not flag.any() or flag.all():
                    continue
                row: dict[str, Any] = {"pair": pair, "source": source}
                for outcome in outcomes:
                    row[outcome] = float(
                        group.loc[flag, outcome].mean()
                        - group.loc[~flag, outcome].mean()
                    )
                rows.append(row)
            contrasts = pd.DataFrame(rows, columns=["pair", "source", *outcomes])
            contrasts_by_side[side] = contrasts
            side_output: dict[str, Any] = {
                "eligible_proofs": int(len(contrasts)),
                "source_groups": int(contrasts.source.nunique()) if len(contrasts) else 0,
            }
            for outcome in outcomes:
                if contrasts.empty:
                    side_output[outcome] = {
                        "flagged_minus_unflagged": None,
                        "source_cluster_ci": [None, None],
                    }
                    continue
                grouped = (
                    contrasts.groupby("source")[outcome].agg(["sum", "size"])
                    .reindex(sources, fill_value=0)
                )
                values = grouped.to_numpy(float)
                draws = rng.integers(0, len(values), size=(n_boot, len(values)))
                sampled = values[draws].sum(axis=1)
                estimates = sampled[:, 0] / np.maximum(sampled[:, 1], 1)
                side_output[outcome] = {
                    "flagged_minus_unflagged": float(contrasts[outcome].mean()),
                    "source_cluster_ci": _ci(estimates),
                }
            output[feature][label] = side_output
        paired = contrasts_by_side["h"].merge(
            contrasts_by_side["a"], on=["pair", "source"],
            suffixes=("_human", "_ai"),
        )
        paired_output: dict[str, Any] = {
            "eligible_pairs": int(len(paired)),
            "source_groups": int(paired.source.nunique()) if len(paired) else 0,
            "estimand": "AI minus human within-proof feature association",
        }
        for outcome in outcomes:
            differences = paired[f"{outcome}_ai"] - paired[f"{outcome}_human"]
            if paired.empty:
                paired_output[outcome] = {
                    "ai_minus_human": None,
                    "source_cluster_ci": [None, None],
                }
                continue
            grouped = (
                pd.DataFrame({"source": paired.source, "difference": differences})
                .groupby("source").difference.agg(["sum", "size"])
                .reindex(sources, fill_value=0)
            )
            values = grouped.to_numpy(float)
            draws = rng.integers(0, len(values), size=(n_boot, len(values)))
            sampled = values[draws].sum(axis=1)
            estimates = sampled[:, 0] / np.maximum(sampled[:, 1], 1)
            paired_output[outcome] = {
                "ai_minus_human": float(differences.mean()),
                "source_cluster_ci": _ci(estimates),
            }
        output[feature]["paired_both_tracks"] = paired_output
    return output


def position_matched_family_associations(
    frame: pd.DataFrame,
    n_boot: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Match family and instance claims by relative position within each proof.

    Earlier claims mechanically have more opportunities for a later lexical
    reference.  Minimum-cost one-to-one matching on normalized claim index asks
    whether the family association survives that basic exposure control.  We
    report both the full optimal match and a conservative quarter-proof caliper.
    Proofs, rather than individual matches, remain the units of the estimand.
    """
    work = frame.copy()
    work["adopted"] = work.explicit_uses.gt(0).astype(float)
    work["multi_uptake"] = work.explicit_uses.gt(1).astype(float)
    outcomes = ("adopted", "multi_uptake", "explicit_uses")
    sources = sorted(work.source.unique())
    result: dict[str, Any] = {
        "feature": "generalized_claim",
        "estimand": (
            "mean family-minus-instance fate after minimum-cost one-to-one matching "
            "on normalized claim position, averaged over eligible proofs"
        ),
    }

    for label, caliper in (("all_matches", None), ("caliper_0_25", 0.25)):
        result[label] = {}
        side_rows: dict[str, pd.DataFrame] = {}
        for side, side_label in (("h", "human"), ("a", "ai")):
            rows: list[dict[str, Any]] = []
            for (pair, source), group in work[work.side.eq(side)].groupby(
                ["pair", "source"]
            ):
                family = group[group.generalized_claim.astype(bool)].copy()
                instance = group[~group.generalized_claim.astype(bool)].copy()
                if family.empty or instance.empty:
                    continue
                scale = max(float(group.claim_index.max()), 1.0)
                family_pos = family.claim_index.to_numpy(float) / scale
                instance_pos = instance.claim_index.to_numpy(float) / scale
                cost = np.abs(family_pos[:, None] - instance_pos[None, :])
                family_i, instance_i = optimize.linear_sum_assignment(cost)
                gaps = cost[family_i, instance_i]
                keep = np.ones(len(gaps), dtype=bool)
                if caliper is not None:
                    keep = gaps <= caliper
                if not keep.any():
                    continue
                family_i, instance_i, gaps = (
                    family_i[keep], instance_i[keep], gaps[keep]
                )
                row: dict[str, Any] = {
                    "pair": pair,
                    "source": source,
                    "matches": int(len(gaps)),
                    "mean_abs_relative_position_gap": float(gaps.mean()),
                }
                for outcome in outcomes:
                    row[outcome] = float(
                        family.iloc[family_i][outcome].to_numpy(float).mean()
                        - instance.iloc[instance_i][outcome].to_numpy(float).mean()
                    )
                rows.append(row)
            contrasts = pd.DataFrame(
                rows,
                columns=[
                    "pair", "source", "matches", "mean_abs_relative_position_gap",
                    *outcomes,
                ],
            )
            side_rows[side] = contrasts
            side_summary: dict[str, Any] = {
                "eligible_proofs": int(len(contrasts)),
                "matched_claim_pairs": int(contrasts.matches.sum()) if len(contrasts) else 0,
                "mean_abs_relative_position_gap": (
                    float(contrasts.mean_abs_relative_position_gap.mean())
                    if len(contrasts) else None
                ),
            }
            for outcome in outcomes:
                if contrasts.empty:
                    side_summary[outcome] = {
                        "family_minus_instance": None,
                        "source_cluster_ci": [None, None],
                    }
                    continue
                grouped = (
                    contrasts.groupby("source")[outcome].agg(["sum", "size"])
                    .reindex(sources, fill_value=0)
                )
                values = grouped.to_numpy(float)
                draws = rng.integers(0, len(values), size=(n_boot, len(values)))
                sampled = values[draws].sum(axis=1)
                estimates = sampled[:, 0] / np.maximum(sampled[:, 1], 1)
                side_summary[outcome] = {
                    "family_minus_instance": float(contrasts[outcome].mean()),
                    "source_cluster_ci": _ci(estimates),
                }
            result[label][side_label] = side_summary

        paired = side_rows["h"].merge(
            side_rows["a"], on=["pair", "source"], suffixes=("_human", "_ai")
        )
        paired_summary: dict[str, Any] = {
            "eligible_pairs": int(len(paired)),
            "estimand": "AI minus human position-matched family association",
        }
        for outcome in outcomes:
            differences = paired[f"{outcome}_ai"] - paired[f"{outcome}_human"]
            if paired.empty:
                paired_summary[outcome] = {
                    "ai_minus_human": None,
                    "source_cluster_ci": [None, None],
                }
                continue
            grouped = (
                pd.DataFrame({"source": paired.source, "difference": differences})
                .groupby("source").difference.agg(["sum", "size"])
                .reindex(sources, fill_value=0)
            )
            values = grouped.to_numpy(float)
            draws = rng.integers(0, len(values), size=(n_boot, len(values)))
            sampled = values[draws].sum(axis=1)
            estimates = sampled[:, 0] / np.maximum(sampled[:, 1], 1)
            paired_summary[outcome] = {
                "ai_minus_human": float(differences.mean()),
                "source_cluster_ci": _ci(estimates),
            }
        result[label]["paired_both_tracks"] = paired_summary
    return result


def interface_coordinate_correlations(frame: pd.DataFrame) -> dict[str, Any]:
    """Proof-level co-movement of distinct human-minus-AI interface proxies."""
    selected = frame[
        frame.h_named_haves.gt(0) & frame.a_named_haves.gt(0)
    ].copy()
    coordinates: dict[str, pd.Series] = {}
    for label, numerator in (
        ("explicit_uses", "explicit_uses"),
        ("long_reach", "long_horizon_haves"),
        ("generalized", "generalized_haves"),
        ("outside_placeholder", "placeholder_haves"),
    ):
        human = selected[f"h_{numerator}"] / selected.h_named_haves
        ai = selected[f"a_{numerator}"] / selected.a_named_haves
        coordinates[label] = (
            (1 - human) - (1 - ai)
            if label == "outside_placeholder" else human - ai
        )
    values = pd.DataFrame(coordinates)
    correlation = values.corr(method="spearman")
    return {
        "pairs_with_claims_on_both_sides": int(len(selected)),
        "coordinate": "human minus AI; outside-placeholder is sign-corrected",
        "spearman": {
            row: {column: float(correlation.loc[row, column]) for column in correlation}
            for row in correlation
        },
    }


def load_pairs(root: Path) -> pd.DataFrame:
    paths = sorted(glob.glob(str(
        root / "census" / "numinamath-proof-artifacts" / "data" / "lite" / "shards" / "*.parquet"
    )))
    if not paths:
        raise FileNotFoundError("NuminaMath proof-artifact shards are not available")
    columns = [
        "uuid", "source", "human_formal_proof", "prover_formal_proof",
        "human_validation_status", "prover_validation_status",
        "human_proof_available", "prover_proof_available",
        "human_ground_truth_type", "human_sorries", "prover_sorries",
        "human_all_tactics", "prover_all_tactics",
        "human_declarations", "prover_declarations",
    ]
    frame = pd.concat(
        [pd.read_parquet(path, columns=columns) for path in paths],
        ignore_index=True,
    )
    candidates = frame[
        frame.human_proof_available
        & frame.prover_proof_available
        & frame.human_validation_status.eq("valid")
        & frame.prover_validation_status.eq("valid")
        & frame.human_ground_truth_type.eq("complete")
    ].drop_duplicates("uuid")
    human_header = candidates.human_declarations.map(serialized_target_signature)
    prover_header = candidates.prover_declarations.map(serialized_target_signature)
    missing = human_header.isna() | prover_header.isna()
    mismatch = ~missing & human_header.ne(prover_header)
    exclusions: list[dict[str, Any]] = []
    for index in candidates.index[missing | mismatch]:
        record = candidates.loc[index]
        exclusions.append({
            "pair": "pair_" + str(record.uuid)[:8],
            "uuid": str(record.uuid),
            "source": str(record.source),
            "reason": "missing_target_declaration" if missing.loc[index] else "mismatched_target_header",
            "human_signature": repr(human_header.loc[index]),
            "prover_signature": repr(prover_header.loc[index]),
        })
    frame = candidates[~missing & ~mismatch].reset_index(drop=True)
    frame.attrs["target_pair_audit"] = {
        "flag_valid_candidates": int(len(candidates)),
        "missing_target_declaration": int(missing.sum()),
        "mismatched_target_header": int(mismatch.sum()),
        "exact_statement_pairs": int(len(frame)),
    }
    frame.attrs["target_pair_exclusions"] = exclusions
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--boot", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260802)
    args = parser.parse_args()

    root = args.root.resolve()
    outdir = root / "results" / "horizon"
    outdir.mkdir(parents=True, exist_ok=True)
    raw = load_pairs(root)
    target_pair_audit = raw.attrs["target_pair_audit"]
    target_pair_exclusions = raw.attrs["target_pair_exclusions"]

    parser_bodies = sum(([
        proof_body(record.human_formal_proof),
        proof_body(record.prover_formal_proof),
    ] for record in raw.itertuples(index=False)), [])
    parsed_have_ranges, have_parser_audit = parser_have_ranges(parser_bodies, root)
    range_index = 0

    proof_rows: list[dict[str, Any]] = []
    claim_rows: list[dict[str, Any]] = []
    for record in raw.itertuples(index=False):
        human_value = serialized_target_value(record.human_declarations)
        ai_value = serialized_target_value(record.prover_declarations)
        human_body_tokens = (
            human_value.split() if human_value is not None
            else proof_body(record.human_formal_proof).split()
        )
        ai_body_tokens = (
            ai_value.split() if ai_value is not None
            else proof_body(record.prover_formal_proof).split()
        )
        human_source_tokens = proof_body(record.human_formal_proof).split()
        ai_source_tokens = proof_body(record.prover_formal_proof).split()
        helper_audits = {
            "h": pretarget_audit(record.human_formal_proof),
            "a": pretarget_audit(record.prover_formal_proof),
        }
        row: dict[str, Any] = {
            "pair": "pair_" + str(record.uuid)[:8],
            "uuid": record.uuid,
            "source": str(record.source),
            "h_pretarget_declarations": helper_audits["h"]["count"],
            "a_pretarget_declarations": helper_audits["a"]["count"],
            "h_used_pretarget_declarations": helper_audits["h"]["used_count"],
            "a_used_pretarget_declarations": helper_audits["a"]["used_count"],
            "h_pretarget_names": "|".join(helper_audits["h"]["names"]),
            "a_pretarget_names": "|".join(helper_audits["a"]["names"]),
            "identical_pretarget_scaffolding": bool(
                helper_audits["h"]["count"]
                and helper_audits["h"]["signature"] == helper_audits["a"]["signature"]
            ),
            "identical_target_value": human_body_tokens == ai_body_tokens,
            "identical_source_body": human_source_tokens == ai_source_tokens,
            "target_value_token_similarity": SequenceMatcher(
                None, human_body_tokens, ai_body_tokens, autojunk=False
            ).ratio(),
        }
        for side, source, tactics in (
            ("h", record.human_formal_proof, record.human_all_tactics),
            ("a", record.prover_formal_proof, record.prover_all_tactics),
        ):
            construction_ranges = parsed_have_ranges[range_index]
            range_index += 1
            row[f"{side}_have_parser_success"] = construction_ranges is not None
            metrics, claims = side_metrics(source, tactics, construction_ranges)
            row.update({f"{side}_{key}": value for key, value in metrics.items()})
            for claim in claims:
                claim_rows.append(
                    {
                        "pair": row["pair"], "source": row["source"], "side": side,
                        **claim,
                    }
                )
        proof_rows.append(row)

    proofs = pd.DataFrame(proof_rows).sort_values("pair")
    claims = pd.DataFrame(claim_rows).sort_values(["pair", "side", "claim_index"])
    gzip = {"method": "gzip", "mtime": 0}
    proofs.to_csv(outdir / "source_pairs.csv.gz", index=False, compression=gzip)
    claims.to_csv(outdir / "claims.csv.gz", index=False, compression=gzip)
    pd.DataFrame(target_pair_exclusions).to_csv(
        outdir / "target_pair_exclusions.csv", index=False
    )

    rng = np.random.default_rng(args.seed)
    metrics = [
        "tokens", "named_haves", "explicit_uses", "zero_uptake_haves",
        "one_uptake_haves", "multi_uptake_haves", "reuse_excess",
        "long_horizon_haves", "total_claim_span", "max_claim_span",
        "total_last_use_delay_tokens",
        "placeholder_haves", "parametric_haves", "universal_haves",
        "generalized_haves", "total_binder_groups",
        "tactic_events", "tactic_types", "used_constants",
    ]
    ai_only_helpers = proofs[
        proofs.a_pretarget_declarations.gt(0) & proofs.h_pretarget_declarations.eq(0)
    ]
    equal_positive_claim_count = (
        proofs.h_named_haves.eq(proofs.a_named_haves) & proofs.h_named_haves.gt(0)
    )
    token_ratio = proofs[["h_tokens", "a_tokens"]].max(axis=1).div(
        proofs[["h_tokens", "a_tokens"]].min(axis=1).clip(lower=1)
    )
    length_within_ten_percent = token_ratio.le(1.10)
    fully_parsed_pairs = proofs[
        proofs.h_have_parser_success
        & proofs.a_have_parser_success
        & proofs.h_parser_unmatched_named_haves.eq(0)
        & proofs.a_parser_unmatched_named_haves.eq(0)
    ]
    have_parser_audit.update({
        "regex_named_claims": int(
            proofs.h_regex_named_haves.sum() + proofs.a_regex_named_haves.sum()
        ),
        "parser_matched_named_claims": int(
            proofs.h_named_haves.sum() + proofs.a_named_haves.sum()
        ),
        "named_claim_coverage": float(
            (proofs.h_named_haves.sum() + proofs.a_named_haves.sum())
            / max(proofs.h_regex_named_haves.sum() + proofs.a_regex_named_haves.sum(), 1)
        ),
        "pairs_fully_parsed_and_aligned": int(len(fully_parsed_pairs)),
    })
    supply_rng = np.random.default_rng(args.seed + 991)
    summary: dict[str, Any] = {
        "seed": args.seed,
        "bootstraps": args.boot,
        "inclusion_rule": (
            "both proofs available; both validation statuses valid; human ground truth complete; "
            "both artifacts contain the same normalized final declaration header; "
            "no outcome-dependent premise filter"
        ),
        "target_pair_audit": target_pair_audit,
        "target_pair_exclusions_file": "results/horizon/target_pair_exclusions.csv",
        "have_scope_parser_audit": have_parser_audit,
        "scope_clipping_audit": {
            "rule": (
                "explicit-use windows end at the tail of the nearest enclosing "
                "tacticSeq, or earlier at a same-name redeclaration"
            ),
            **{
                label: {
                    "claims": int(len(selected)),
                    "claims_in_nested_scope": int(selected.scope_clipped.sum()),
                    "claims_with_excluded_name_tokens": int(
                        selected.scope_excluded_reference_tokens.gt(0).sum()
                    ),
                    "excluded_name_tokens": int(
                        selected.scope_excluded_reference_tokens.sum()
                    ),
                    "unscoped_uses_per_claim": float(
                        selected.unscoped_explicit_uses.mean()
                    ),
                    "scoped_uses_per_claim": float(selected.explicit_uses.mean()),
                    "unscoped_zero_share": float(
                        selected.unscoped_explicit_uses.eq(0).mean()
                    ),
                    "scoped_zero_share": float(selected.explicit_uses.eq(0).mean()),
                    "unscoped_multi_share": float(
                        selected.unscoped_explicit_uses.gt(1).mean()
                    ),
                    "scoped_multi_share": float(selected.explicit_uses.gt(1).mean()),
                }
                for label, selected in (
                    ("human", claims[claims.side.eq("h")]),
                    ("ai", claims[claims.side.eq("a")]),
                )
            },
        },
        "dataset_provenance": {
            "source": "https://huggingface.co/datasets/AI-MO/NuminaMath-LEAN",
            "huggingface_revision": huggingface_revisions(root),
            "files": [
                {
                    "path": str(path.relative_to(root)),
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
                for path in sorted(
                    (root / "census" / "numinamath-proof-artifacts" / "data" / "lite" / "shards").glob("*.parquet")
                )
            ],
        },
        "pairs": len(proofs),
        "source_groups": int(proofs.source.nunique()),
        "paired": {metric: paired_metric(proofs, metric, args.boot, rng) for metric in metrics},
        "claim_rates": {},
        "claim_supply_per_100_tokens": {
            metric: token_supply_difference(
                proofs, numerator, args.boot, supply_rng
            )
            for metric, numerator in (
                ("all_named", "named_haves"),
                ("adopted_at_least_once", "adopted_haves"),
                ("multiply_retrieved", "multi_uptake_haves"),
                ("descriptively_named", "descriptively_named_haves"),
                ("generalized", "generalized_haves"),
            )
        },
        "name_lexicon": {
            "human": name_lexicon(claims, "h"),
            "ai": name_lexicon(claims, "a"),
        },
        "parametric_claim_profiles": {
            "human": flagged_claim_profile(claims, "h", "parametric_claim"),
            "ai": flagged_claim_profile(claims, "a", "parametric_claim"),
        },
        "generalized_claim_profiles": {
            "human": flagged_claim_profile(claims, "h", "generalized_claim"),
            "ai": flagged_claim_profile(claims, "a", "generalized_claim"),
        },
        "within_proof_feature_associations": within_proof_feature_associations(
            claims, args.boot, rng
        ),
        "position_matched_family_associations": position_matched_family_associations(
            claims, args.boot, rng
        ),
        "interface_coordinate_correlations": interface_coordinate_correlations(proofs),
        "uptake_reach_decomposition": uptake_reach_decomposition(
            claims, args.boot, rng
        ),
        "uptake_reach_matched_controls": {
            "exact_equal_positive_claim_count": {
                "pairs": int(equal_positive_claim_count.sum()),
                "profile": uptake_reach_decomposition(
                    claims[claims.pair.isin(proofs.loc[
                        equal_positive_claim_count, "pair"
                    ])],
                    args.boot, rng,
                ),
            },
            "within_ten_percent_length": {
                "pairs": int(length_within_ten_percent.sum()),
                "profile": uptake_reach_decomposition(
                    claims[claims.pair.isin(proofs.loc[
                        length_within_ten_percent, "pair"
                    ])],
                    args.boot, rng,
                ),
            },
        },
        "pretarget_declaration_audit": {
            "human_artifacts_with_helpers": int(proofs.h_pretarget_declarations.gt(0).sum()),
            "ai_artifacts_with_helpers": int(proofs.a_pretarget_declarations.gt(0).sum()),
            "both_tracks_with_helpers": int(
                (proofs.h_pretarget_declarations.gt(0) & proofs.a_pretarget_declarations.gt(0)).sum()
            ),
            "identical_shared_scaffolding": int(proofs.identical_pretarget_scaffolding.sum()),
            "human_only": int(
                (proofs.h_pretarget_declarations.gt(0) & proofs.a_pretarget_declarations.eq(0)).sum()
            ),
            "ai_only": int(
                (proofs.a_pretarget_declarations.gt(0) & proofs.h_pretarget_declarations.eq(0)).sum()
            ),
            "ai_only_artifacts_referencing_helper": int(
                ai_only_helpers.a_used_pretarget_declarations.gt(0).sum()
            ),
            "ai_only_helper_names": sorted({
                name
                for names in ai_only_helpers.a_pretarget_names
                for name in str(names).split("|") if name
            }),
            "human_helper_declarations": int(proofs.h_pretarget_declarations.sum()),
            "ai_helper_declarations": int(proofs.a_pretarget_declarations.sum()),
            "human_helpers_referenced_by_target": int(proofs.h_used_pretarget_declarations.sum()),
            "ai_helpers_referenced_by_target": int(proofs.a_used_pretarget_declarations.sum()),
        },
        "claim_count_sensitivity": claim_count_sensitivity(
            proofs, args.boot, rng
        ),
        "length_matched_sensitivity": length_matched_sensitivity(
            proofs, args.boot, rng
        ),
        "nonredeclared_name_sensitivity": nonredeclared_name_sensitivity(
            claims, args.boot, rng
        ),
        "fully_parsed_pair_sensitivity": {
            "rule": (
                "retain pairs for which both proof values parse and every "
                "regex-detected named have has an exact parser range"
            ),
            "pairs": int(len(fully_parsed_pairs)),
            **{
                metric: claim_rate_difference(
                    fully_parsed_pairs, numerator, args.boot, rng
                )
                for metric, numerator in (
                    ("explicit_uses_per_claim", "explicit_uses"),
                    ("zero_uptake_share", "zero_uptake_haves"),
                    ("multi_uptake_share", "multi_uptake_haves"),
                    ("long_horizon_share", "long_horizon_haves"),
                )
            },
        },
        "parametric_claim_difference": claim_rate_difference(
            proofs, "parametric_haves", args.boot, rng
        ),
        "universal_claim_difference": claim_rate_difference(
            proofs, "universal_haves", args.boot, rng
        ),
        "generalized_claim_difference": claim_rate_difference(
            proofs, "generalized_haves", args.boot, rng
        ),
        "binder_groups_per_claim_difference": claim_rate_difference(
            proofs, "total_binder_groups", args.boot, rng
        ),
    }
    human_parametric = proofs.h_parametric_haves.gt(0)
    ai_parametric = proofs.a_parametric_haves.gt(0)
    summary["parametric_proof_pair_audit"] = {
        "human_any": int(human_parametric.sum()),
        "ai_any": int(ai_parametric.sum()),
        "both": int((human_parametric & ai_parametric).sum()),
        "human_only": int((human_parametric & ~ai_parametric).sum()),
        "ai_only": int((ai_parametric & ~human_parametric).sum()),
        "neither": int((~human_parametric & ~ai_parametric).sum()),
    }
    human_generalized = proofs.h_generalized_haves.gt(0)
    ai_generalized = proofs.a_generalized_haves.gt(0)
    summary["generalized_proof_pair_audit"] = {
        "human_any": int(human_generalized.sum()),
        "ai_any": int(ai_generalized.sum()),
        "both": int((human_generalized & ai_generalized).sum()),
        "human_only": int((human_generalized & ~ai_generalized).sum()),
        "ai_only": int((ai_generalized & ~human_generalized).sum()),
        "neither": int((~human_generalized & ~ai_generalized).sum()),
    }
    summary["automation_exclusion_sensitivity"] = {}
    for tactic in ("native_decide", "decide", "norm_num", "aesop"):
        subset = proofs[
            proofs[f"h_source_tactic_{tactic}"].eq(0)
            & proofs[f"a_source_tactic_{tactic}"].eq(0)
        ]
        summary["automation_exclusion_sensitivity"][tactic] = {
            "rule": f"exclude pairs where either target proof contains {tactic}",
            "pairs": int(len(subset)),
            "generalized_claim_share": claim_rate_difference(
                subset, "generalized_haves", args.boot, rng
            ),
        }
    for side, label in (("h", "human"), ("a", "ai")):
        summary["claim_rates"][label] = {
            "explicit_uses_per_claim": claim_rate(
                proofs, side, "explicit_uses", args.boot, rng),
            "zero_uptake_share": claim_rate(
                proofs, side, "zero_uptake_haves", args.boot, rng),
            "one_uptake_share": claim_rate(
                proofs, side, "one_uptake_haves", args.boot, rng),
            "multi_uptake_share": claim_rate(
                proofs, side, "multi_uptake_haves", args.boot, rng),
            "long_horizon_share": claim_rate(
                proofs, side, "long_horizon_haves", args.boot, rng),
            "placeholder_name_share": claim_rate(
                proofs, side, "placeholder_haves", args.boot, rng),
            "parametric_claim_share": claim_rate(
                proofs, side, "parametric_haves", args.boot, rng),
            "universal_claim_share": claim_rate(
                proofs, side, "universal_haves", args.boot, rng),
            "generalized_claim_share": claim_rate(
                proofs, side, "generalized_haves", args.boot, rng),
            "binder_groups_per_claim": claim_rate(
                proofs, side, "total_binder_groups", args.boot, rng),
        }

    low_overlap = proofs[proofs.target_value_token_similarity.lt(0.9)]
    summary["target_value_overlap_audit"] = {
        "similarity": "SequenceMatcher ratio over comment/string-stripped structured proof-value whitespace tokens",
        "identical_pairs": int(proofs.identical_target_value.sum()),
        "similarity_at_least_0_9": int(proofs.target_value_token_similarity.ge(0.9).sum()),
        "median_similarity": float(proofs.target_value_token_similarity.median()),
        "sensitivity_excluding_similarity_at_least_0_9": {
            "pairs": int(len(low_overlap)),
            **{
                metric: claim_rate_difference(low_overlap, numerator, args.boot, rng)
                for metric, numerator in (
                    ("explicit_uses_per_claim", "explicit_uses"),
                    ("zero_uptake_share", "zero_uptake_haves"),
                    ("multi_uptake_share", "multi_uptake_haves"),
                    ("long_horizon_share", "long_horizon_haves"),
                    ("placeholder_name_share", "placeholder_haves"),
                )
            },
        },
    }

    value_matched = proofs[proofs.identical_target_value]
    value_matched_source_different = value_matched[~value_matched.identical_source_body]
    summary["certificate_rendering_match_audit"] = {
        "criterion": "token-identical comment-stripped structured target proof-value rendering",
        "pairs": int(len(value_matched)),
        "source_body_also_identical": int(value_matched.identical_source_body.sum()),
        "source_body_different": int(len(value_matched_source_different)),
        "different_source_named_haves": {
            "human": int(value_matched_source_different.h_named_haves.sum()),
            "ai": int(value_matched_source_different.a_named_haves.sum()),
        },
    }

    by_source: list[dict[str, Any]] = []
    for source, group in proofs.groupby("source"):
        row = {"source": source, "n_pairs": len(group)}
        for metric in ("named_haves", "used_constants", "tokens"):
            row[f"delta_{metric}"] = float(
                np.median(group[f"a_{metric}"] - group[f"h_{metric}"])
            )
        for side, label in (("h", "human"), ("a", "ai")):
            source_claims = claims[
                claims.source.eq(source) & claims.side.eq(side)
            ]
            adopted_claims = source_claims[source_claims.explicit_uses.gt(0)]
            normalized_claims = adopted_claims[
                adopted_claims.fraction_available_claims_to_last_use.notna()
            ]
            row[f"{label}_explicit_uses_per_claim"] = float(
                group[f"{side}_explicit_uses"].sum()
                / max(group[f"{side}_named_haves"].sum(), 1)
            )
            row[f"{label}_zero_uptake_share"] = float(
                group[f"{side}_zero_uptake_haves"].sum()
                / max(group[f"{side}_named_haves"].sum(), 1)
            )
            row[f"{label}_long_horizon_share"] = float(
                group[f"{side}_long_horizon_haves"].sum()
                / max(group[f"{side}_named_haves"].sum(), 1)
            )
            row[f"{label}_adoption_probability"] = float(
                source_claims.explicit_uses.gt(0).mean()
            )
            row[f"{label}_last_use_token_distance_given_adoption"] = float(
                adopted_claims.last_use_delay_tokens.mean()
            )
            row[f"{label}_fraction_available_boundaries_crossed_given_adoption"] = float(
                normalized_claims.fraction_available_claims_to_last_use.mean()
            )
            row[f"{label}_parametric_claim_share"] = float(
                group[f"{side}_parametric_haves"].sum()
                / max(group[f"{side}_named_haves"].sum(), 1)
            )
            row[f"{label}_generalized_claim_share"] = float(
                group[f"{side}_generalized_haves"].sum()
                / max(group[f"{side}_named_haves"].sum(), 1)
            )
        by_source.append(row)
    pd.DataFrame(by_source).sort_values("source").to_csv(outdir / "by_source.csv", index=False)
    summary["by_source_file"] = "results/horizon/by_source.csv"

    # A coarse tactic-family sensitivity: within pairs where both sides invoke
    # a tactic at least once, and within pairs where neither side does.
    tactic_strata: list[dict[str, Any]] = []
    for tactic in ("linarith", "nlinarith", "norm_num", "omega", "ring", "simp"):
        human_uses = proofs[f"h_event_{tactic}"].gt(0)
        ai_uses = proofs[f"a_event_{tactic}"].gt(0)
        for stratum, mask in (("both_use", human_uses & ai_uses),
                              ("neither_uses", ~human_uses & ~ai_uses)):
            group = proofs[mask]
            if group.empty:
                continue
            row = {"tactic": tactic, "stratum": stratum, "n_pairs": len(group)}
            for side, label in (("h", "human"), ("a", "ai")):
                denominator = max(group[f"{side}_named_haves"].sum(), 1)
                row[f"{label}_explicit_uses_per_claim"] = float(
                    group[f"{side}_explicit_uses"].sum() / denominator
                )
                row[f"{label}_zero_uptake_share"] = float(
                    group[f"{side}_zero_uptake_haves"].sum() / denominator
                )
            tactic_strata.append(row)
    pd.DataFrame(tactic_strata).to_csv(outdir / "tactic_matched_strata.csv", index=False)
    summary["tactic_sensitivity_file"] = "results/horizon/tactic_matched_strata.csv"

    with (outdir / "source_summary.json").open("w") as stream:
        json.dump(summary, stream, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
