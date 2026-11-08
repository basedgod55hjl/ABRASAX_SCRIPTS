// helpers/patch_rebuild_empty_mirror.mjs — an empty mirror must recreate an
// empty repo, not be reported as a failed restore.
import { readFileSync, writeFileSync, copyFileSync } from "node:fs";

const P = "C:/ABRASAX/SCRIPTS/rebuild_repos.py";
let s = readFileSync(P, "utf8");
if (s.includes("recreated empty")) { console.log("already patched"); process.exit(0); }
const OLD = '    url = f"https://github.com/{repo.OWNER_DEFAULT}/{name}.git"';
if (s.split(OLD).length - 1 !== 1) throw new Error("anchor missing or ambiguous");
const NEW = `    refs = repo.run(["git", "-C", str(mirror), "for-each-ref", "--format=%(refname)"], timeout=300)
    if not [x for x in refs["stdout"].splitlines() if x.strip()]:
        # it was empty before deletion; recreate it empty and say so, don't fake a SHA
        return {"repo": name, "state": "restored", "remote_sha": None, "branch": branch,
                "matches": True, "note": "repo was empty; recreated empty"}
    url = f"https://github.com/{repo.OWNER_DEFAULT}/{name}.git"`;
copyFileSync(P, P + ".bak-emptymirror");
writeFileSync(P, s.replace(OLD, NEW));
console.log("patched " + P);
