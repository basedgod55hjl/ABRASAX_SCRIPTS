from pathlib import Path

p = Path(r"C:\abrasax\DOC\RUN-STATE-20261101T1735Z.md")
s = p.read_text(encoding="utf-8")

old = """Two things a later pass must decide, because they need an explicit index
operation (`git rm -r --cached …`), not an ignore rule:

1. `UnityProjects/ABRASAX-UIBench/Library` is **tracked**. Ignoring the
   directory stops new files but does not untrack the old ones, so every Unity
   run still dirties the tree.
2. `UI/upstream/InputSystem` is a **submodule** whose worktree is dirty: its
   index already carries thousands of staged deletions from an earlier session.
   The parent can only record a pointer, so that state stays unresolved until
   someone commits (or resets) inside the submodule."""

new = """One of the two needed an explicit index operation rather than an ignore rule,
and `FINDINGS_UNITY_CSPROJ.md` (session 030853ff53b1ea0a) had already measured
it:

1. `UnityProjects/ABRASAX-UIBench/Library` was **tracked** - 1,424 files /
   69.1 MB (662 `.meta`, 448 `.cs` from `Library/PackageCache`, 88 `.bhc`
   shader caches, 51 `.asmdef`, 51 `.json`, plus 8 ScriptAssemblies
   `.dll/.pdb`). Ignoring alone would not have untracked it. Now removed from
   the index only (`git rm -r --cached`, commit `a87b89e`): 1,668 files remain
   on disk and Unity re-imports them on next open. Ignore rules were widened to
   `UnityProjects/**/...` so a nested project is covered too.
2. `UI/upstream/InputSystem` is a **submodule** whose own index already carries
   thousands of staged deletions from an earlier session. The parent can only
   record a pointer, so that state stays unresolved until someone commits (or
   resets) inside the submodule. Not touched here."""

assert s.count(old) == 1
s = s.replace(old, new, 1)

old2 = """```
196ee0e  feat(run): start-all verb, checkpoint recovery, and honest run signals
facba3f  chore(repo): ignore Unity-generated caches; add ABRASAX-CLI-Demo source
```

573 files / +33,215 lines in the first; 82 files in the second."""
new2 = """```
196ee0e  feat(run): start-all verb, checkpoint recovery, and honest run signals
facba3f  chore(repo): ignore Unity-generated caches; add ABRASAX-CLI-Demo source
a87b89e  chore(repo): untrack Unity-generated Library (1,424 files / 69.1 MB)
```

573 files / +33,215 lines in the first; 82 files in the second; 1,424 index-only
deletions in the third."""
assert s.count(old2) == 1
s = s.replace(old2, new2, 1)

old3 = "git log -1                     facba3f (main, 5 commits ahead of origin/main)"
new3 = "git log -1                     a87b89e (main, 6 commits ahead of origin/main)"
assert s.count(old3) == 1
s = s.replace(old3, new3, 1)

p.write_text(s, encoding="utf-8", newline="")
print("doc updated for a87b89e")
