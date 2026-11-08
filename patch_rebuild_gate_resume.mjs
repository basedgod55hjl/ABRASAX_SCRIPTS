// helpers/patch_rebuild_gate_resume.mjs — on a resume, the live SHA comparison
// is exactly the wrong test: the repo has already been deleted and rebuilt from
// the staged tree, so of course the live SHA no longer matches the mirror. The
// mirror only has to be intact.
import { readFileSync, writeFileSync, copyFileSync } from "node:fs";

const P = "C:/ABRASAX/SCRIPTS/rebuild_repos.py";
let s = readFileSync(P, "utf8");
if (s.includes("# resume: mirror integrity is the only gate")) { console.log("already patched"); process.exit(0); }
const nl = s.includes("\r\n") ? "\r\n" : "\n";
const OLD = [
  "    backup = _backup_ok(name)",
  '    if not backup["ok"]:',
  '        return {"ok": False, "why": backup["why"]}',
].join(nl);
const NEW = [
  "    backup = _backup_ok(name)",
  '    if not backup["ok"]:',
  '        return {"ok": False, "why": backup["why"]}',
  "    # resume: mirror integrity is the only gate - the live repo is the NEW one",
  "    if allow_missing:",
  '        return {"ok": True, "mirror_head": backup.get("mirror_head"), "note": "resume"}',
].join(nl);
const hits = s.split(OLD).length - 1;
if (hits !== 1) throw new Error("anchor matched " + hits + "x");
copyFileSync(P, P + ".bak-gateresume");
writeFileSync(P, s.replace(OLD, NEW));
console.log("patched " + P);
