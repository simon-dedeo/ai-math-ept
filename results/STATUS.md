# Overnight run status — updated 2026-07-31 15:37:20

Historical status snapshot. The output paths below were programmatically generated and were removed
from the compact checkout after validation.

| stage | state | output |
|---|---|---|
| study2 comparison (AI vs human proofs) | pending | results/study2_main/ |
| study6 ETP provenance (who builds hubs) | DONE | results/study6/ |
| study7 automation dose-response | DONE | results/study7/ |
| study8 source-level cross-project | DONE | results/study8/ |
| study9 matched-pair EPT sims | pending | results/study9/ |

Tail of log:
```

=== summary ===
                           corpus authorship  n_decls  n_edges  modularity_Q  alpha_reuse  frac_never_cited  reuse_gini  belief_eps0.01
sphere_packing_HUMAN(pre-Feb2026)      human     1026     3385         0.509        2.030          0.306043    0.808350          0.9805
   sphere_packing_GAUSS(math-inc)         AI     5676    32596         0.514        1.959          0.198732    0.833556          0.9882
                  strongPNT_GAUSS         AI     1110     2007         0.794        2.366          0.184685    0.583150          0.8978
                        pfr_HUMAN      human      977     2649         0.602        2.257          0.267144    0.699493          0.9446
                        FLT_HUMAN      human     2949    13828         0.455        2.094          0.330960    0.865553          0.9802
                       PNT+_HUMAN      human     8287    46606         0.532        1.663          0.250030    0.873134          0.9936
                  ETP_human_files      human     2153    10141         0.488        1.907          0.456108    0.892097          0.9889
              ETP_generated_files    machine    11046     4635         0.145        2.036          0.983252    0.998792          0.5418
                  compfiles_HUMAN      human     3337    18902         0.470        1.888          0.273899    0.861649          0.9861
                   seed_prover_AI         AI     6030    15403         0.673        1.976          0.417910    0.839777          0.9506
                     aristotle_AI         AI      125      371         0.625        1.939          0.216000    0.704259          0.9573
              alphaproof_nexus_AI         AI     3007    10032         0.698        2.073          0.189558    0.750199          0.9757

=== by authorship ===
            modularity_Q  alpha_reuse  frac_never_cited  reuse_gini  belief_eps0.01
authorship                                                                         
AI                 0.661        2.063             0.241       0.742           0.954
human              0.509        1.973             0.314       0.833           0.979
machine            0.145        2.036             0.983       0.999           0.542
done 48s
=== [2026-07-31 15:37:20] END study8_source_graphs (rc=0)
=== [2026-07-31 15:37:20] START study9_matched_pairs
```
