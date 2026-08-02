"""Regressions for within-proof, position-matched binder fate contrasts."""
from __future__ import annotations

import numpy as np
import pandas as pd

from analyze_binder_use import position_matched_generality_term_association


def test_position_caliper_filters_distant_family_instance_match() -> None:
    rows = []
    for side in ("h", "a"):
        for position, family, zero, one, multi in (
            (0, True, 0, 0, 1),
            (9, True, 0, 1, 0),
            (1, False, 1, 0, 0),
            (5, False, 0, 1, 0),
        ):
            rows.append({
                "pair": "p",
                "side": side,
                "source": "s",
                "claim_index": position,
                "source_claims_in_proof": 10,
                "generalized_claim": family,
                "zero_term_use": zero,
                "one_term_use": one,
                "multi_term_use": multi,
            })
    summary = position_matched_generality_term_association(
        pd.DataFrame(rows), np.random.default_rng(7), 100
    )["caliper_0_25"]
    for side in ("human", "ai"):
        assert summary[side]["eligible_proofs"] == 1
        assert summary[side]["matched_claim_pairs"] == 1
        assert summary[side]["multi_term_use"]["family_minus_instance"] == 1
        assert summary[side]["zero_term_use"]["family_minus_instance"] == -1
    assert summary["paired_both_tracks"]["eligible_pairs"] == 1
    assert summary["paired_both_tracks"]["multi_term_use"]["ai_minus_human"] == 0


if __name__ == "__main__":
    test_position_caliper_filters_distant_family_instance_match()
    print("binder generality tests passed")
