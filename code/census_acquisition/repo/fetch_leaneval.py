import json, glob, os, re, urllib.request, collections

BASE = os.path.expanduser("~/ai_math_ept/census")
OUT = BASE + "/lean-eval-submissions/proofs"
os.makedirs(OUT, exist_ok=True)
SAFE = re.compile(r"[^A-Za-z0-9_.-]")


def get(u):
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "census"})
        return urllib.request.urlopen(req, timeout=30).read().decode("utf8", "replace")
    except Exception:
        return None


rows = []
ok = 0
fail = 0
for f in glob.glob(BASE + "/lean-eval-submissions/results/*.json"):
    user = os.path.basename(f)[:-5]
    d = json.load(open(f))
    for system, probs in (d.get("solved") or {}).items():
        for prob, m in probs.items():
            if not m.get("submission_public"):
                continue
            repo = m.get("submission_repo")
            ref = m.get("submission_ref")
            kind = m.get("submission_kind")
            txt = None
            if kind == "gist":
                txt = get("https://gist.githubusercontent.com/%s/raw/%s/Submission.lean" % (repo, ref))
            else:
                for p in ("generated/%s/Submission.lean" % prob,
                          "%s/Submission.lean" % prob,
                          "Submission.lean"):
                    txt = get("https://raw.githubusercontent.com/%s/%s/%s" % (repo, ref, p))
                    if txt:
                        break
            safesys = SAFE.sub("_", system)[:60]
            if txt and ("theorem" in txt or "lemma" in txt):
                dd = OUT + "/" + safesys
                os.makedirs(dd, exist_ok=True)
                open(dd + "/" + SAFE.sub("_", prob) + ".lean", "w").write(txt)
                ok += 1
                st = "ok"
            else:
                fail += 1
                st = "miss"
            rows.append(dict(user=user, system=system, problem=prob, kind=kind,
                             repo=repo, ref=ref, status=st))

json.dump(rows, open(BASE + "/lean-eval-submissions/fetch_index.json", "w"), indent=1)
print("fetched", ok, "missed", fail)
print(collections.Counter(r["system"] for r in rows if r["status"] == "ok").most_common(25))
