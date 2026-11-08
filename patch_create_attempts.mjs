// helpers/patch_create_attempts.mjs — one create attempt per round is the
// gentler strategy: GitHub's secondary limit punishes retry storms, and 8
// in-process retries per repo would spend ~27 min on one repo before moving on.
// The supervisor loop (rebuild_retry.py) already provides the patience.
import { readFileSync, writeFileSync, copyFileSync } from "node:fs";

const P = "C:/ABRASAX/SCRIPTS/rebuild_repos.py";
let s = readFileSync(P, "utf8");
if (s.includes("ABX_CREATE_ATTEMPTS")) { console.log("already patched"); process.exit(0); }
const nl = s.includes("\r\n") ? "\r\n" : "\n";

const OLD = [
  'def create_with_retry(name: str, private: bool, description: str, attempts: int = 8) -> dict:',
  '    """repo.create, but survive GitHub\'s secondary rate limit (it is temporary)."""',
  "    last = None",
  "    for i in range(attempts):",
].join(nl);

const NEW = [
  'def create_with_retry(name: str, private: bool, description: str, attempts: int | None = None) -> dict:',
  '    """repo.create, but survive GitHub\'s secondary rate limit (it is temporary)."""',
  "    if attempts is None:",
  "        # the supervisor decides how patient to be; a retry storm makes it worse",
  '        attempts = int(os.environ.get("ABX_CREATE_ATTEMPTS", "8"))',
  "    last = None",
  "    for i in range(attempts):",
].join(nl);

const hits = s.split(OLD).length - 1;
if (hits !== 1) throw new Error("anchor matched " + hits + "x");
let out = s.replace(OLD, NEW);
if (!new RegExp("^import os$", "m").test(out)) {
  const importAnchor = ["import argparse", "import json", "import sys"].join(nl);
  if (out.split(importAnchor).length - 1 !== 1) throw new Error("import anchor missing");
  out = out.replace(importAnchor, ["import argparse", "import json", "import os", "import sys"].join(nl));
}
copyFileSync(P, P + ".bak-attempts");
writeFileSync(P, out);
console.log("patched " + P);
