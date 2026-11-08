// helpers/patch_verify_restored_empty.mjs — an empty repo is not a mismatch.
// ABRASAX_DATA was created empty, was empty when deleted, and is empty again.
// Comparing HEADs there reports a false failure, which trains you to ignore the
// check - the worst possible outcome for a verifier.
import { readFileSync, writeFileSync, copyFileSync } from "node:fs";

const P = "C:/ABRASAX/SCRIPTS/verify_restored.py";
let s = readFileSync(P, "utf8");
if (s.includes("EMPTY both sides")) { console.log("already patched"); process.exit(0); }
const nl = s.includes("\r\n") ? "\r\n" : "\n";
const OLD = "        if name not in live:";
const NEW = [
  "        if not mirror_head:",
  "            # an empty repo is not a failure: nothing to compare, and it was empty before",
  "            present = name in live",
  '            print(f"{name:<24} EMPTY both sides (present_on_github={present})")',
  "            ok_all = ok_all and present",
  "            continue",
  "        if name not in live:",
].join(nl);
const hits = s.split(OLD).length - 1;
if (hits !== 1) throw new Error("anchor matched " + hits + "x");
copyFileSync(P, P + ".bak-empty");
writeFileSync(P, s.replace(OLD, NEW));
console.log("patched " + P);
