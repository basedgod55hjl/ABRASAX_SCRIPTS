// helpers/patch_rebuild_resume.mjs — make --skip-delete resumable.
// The gate required mirror HEAD == LIVE remote SHA, which is meaningless once
// the repo is already deleted (it cannot be on the account). On a resume the
// only thing that matters is that the mirror is intact.
import { readFileSync, writeFileSync, copyFileSync } from "node:fs";

const P = "C:/ABRASAX/SCRIPTS/rebuild_repos.py";
let s = readFileSync(P, "utf8");
if (s.includes("allow_missing")) { console.log("already patched"); process.exit(0); }

const nl = s.includes("\r\n") ? "\r\n" : "\n";
const pairs = [
  [
    ["def gate(name: str, live: dict) -> dict:",
     '    """Every reason a delete would be unsafe, checked against the live account."""',
     "    if name not in live:",
     '        return {"ok": False, "why": "not on the account"}'].join(nl),
    ["def gate(name: str, live: dict, allow_missing: bool = False) -> dict:",
     '    """Every reason a delete would be unsafe, checked against the live account."""',
     "    if name not in live:",
     "        if allow_missing:",
     '            # resume path: the repo is already gone, only the mirror can be checked',
     "            backup = _backup_ok(name)",
     '            return {"ok": backup["ok"], "why": backup.get("why", ""), ',
     '                    "mirror_head": backup.get("mirror_head"), "note": "already deleted"}',
     '        return {"ok": False, "why": "not on the account"}'].join(nl),
  ],
  [
    "    gates = {n: gate(n, live) for n in targets}",
    "    gates = {n: gate(n, live, allow_missing=args.skip_delete) for n in targets}",
  ],
];

for (const [from, to] of pairs) {
  const hits = s.split(from).length - 1;
  if (hits !== 1) throw new Error("anchor matched " + hits + "x: " + from.slice(0, 60));
  s = s.replace(from, to);
}
copyFileSync(P, P + ".bak-resume");
writeFileSync(P, s);
console.log("patched " + P);
