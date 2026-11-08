from pathlib import Path

p = Path(r"C:\abrasax\DOC\RUN-STATE-20261101T1735Z.md")
s = p.read_text(encoding="utf-8")
assert "## 7. Add all" not in s

s += """
---

## 7. Add all — `git add -A` and what it found

`git add -A` on this tree did **not** finish: it ran CPU-bound for over ten
minutes, twice, and had to be killed (index lock left behind, removed by hand).
The cause is not size in bytes but file count: `UnityProjects/ABRASAX-CLI-Demo`
is **25,337 files / 1.29 GB**, almost all `Library/` (ArtifactDB, Bee traces,
shader caches) plus Unity/VS-generated `.csproj`/`.slnx`, and
`UnityProjects/ABRASAX-UIBench/Library` is already tracked and churns. With
`core.autocrlf=true` every one of those files is scanned for line endings, so
the add never converged.

What was done instead:

* staged everything except `UnityProjects` — **589 files in 2.1 s**;
* staged the Unity project **source** after ignoring what Unity regenerates —
  `Library/ Temp/ Logs/ obj/ UserSettings/ *.csproj *.slnx *.sln` — which left
  73 source files;
* root-level session debris (`_*.err`, `_final_probe.txt`, a zero-byte file
  named ``200`n-``, `source_kind`) is now ignored rather than committed;
* every staged tree was scanned by `SCRIPTS/_scan_staged_for_secrets.py`
  (index only, never the working tree): **0 hits** for `github_pat_`, `ghp_`,
  `sk-`, `AKIA`, private-key headers.

Commits:

```
196ee0e  feat(run): start-all verb, checkpoint recovery, and honest run signals
facba3f  chore(repo): ignore Unity-generated caches; add ABRASAX-CLI-Demo source
```

573 files / +33,215 lines in the first; 82 files in the second.

Two things a later pass must decide, because they need an explicit index
operation (`git rm -r --cached …`), not an ignore rule:

1. `UnityProjects/ABRASAX-UIBench/Library` is **tracked**. Ignoring the
   directory stops new files but does not untrack the old ones, so every Unity
   run still dirties the tree.
2. `UI/upstream/InputSystem` is a **submodule** whose worktree is dirty: its
   index already carries thousands of staged deletions from an earlier session.
   The parent can only record a pointer, so that state stays unresolved until
   someone commits (or resets) inside the submodule.

## 8. Final state at the end of this pass

```
git log -1                     facba3f (main, 5 commits ahead of origin/main)
python -m pytest -q            352 passed, 2 skipped   (165.91 s)
verify_stack_run.py            STACK RUN: OK up=16 down=3 failed=0
ops-state.json                 signature "healthy", heals [], queue 0
services                       17/20 up; down = comfyui, imagegen (absent tree),
                               vlc-7d-sampler (external, optional)
gateway E2E                    "OSIRISBLXCK-CLOSED", 36 tokens
:8083/v1/embeddings            2048 dims
```

Nothing was pushed: `origin/main` is 5 commits behind, and publishing needs the
token that item 7 of section 5 says must be rotated first.
"""
p.write_text(s, encoding="utf-8", newline="")
print("doc updated")
