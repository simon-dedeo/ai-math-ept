import sys, os
from huggingface_hub import snapshot_download
repo=sys.argv[1]; dest=sys.argv[2]; pats=sys.argv[3].split(",") if len(sys.argv)>3 else None
os.makedirs(dest, exist_ok=True)
p=snapshot_download(repo_id=repo, repo_type="dataset", local_dir=dest,
                    allow_patterns=pats, max_workers=8)
print("DONE", p)
