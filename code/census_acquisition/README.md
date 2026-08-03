# Corpus acquisition recipes

These small scripts were retained from the local census workspace before its reproducible corpus
checkouts and downloads were removed to save disk space. The `repo/` scripts clone public source
repositories and extract standalone proofs; the `hf/` scripts fetch and index Hugging Face corpora.
They are historical acquisition recipes and still contain the original workstation paths, so set
their `BASE` variables for a new machine before running them.

For the current horizon paper, use the portable pinned downloader instead:

```bash
python code/fetch_horizon_data.py
```

It downloads only the five lite NuminaMath-LEAN artifact shards and verifies their recorded SHA-256
digests.
