// helpers/patch_sync_readback_retry.mjs — a push proof must tolerate API lag.
// Incident: ABRASAX-System32-AI reported matches=false immediately after a
// successful force push. Re-reading a few seconds later showed remote == local.
// GitHub's commits API is eventually consistent right after a push, so a single
// read-back turns a success into a failure and sends you debugging a push that
// worked.
import { readFileSync, writeFileSync, copyFileSync } from "node:fs";

const P = "C:/ABRASAX/tools/abx/repo.py";
let s = readFileSync(P, "utf8");
if (s.includes("read the remote back, patiently")) { console.log("already patched"); process.exit(0); }
const nl = s.includes("\r\n") ? "\r\n" : "\n";

const OLD = [
  "    if slug:",
  "        after = remote_head(slug, branch)",
  "        r.add(remote=slug, remote_branch=branch, remote_sha=after.get(\"sha\"),",
  "              matches=after.get(\"sha\") == local_sha)",
  "        if after.get(\"sha\") != local_sha:",
  "            r.ok = False",
  "            r.errors.append(\"remote SHA does not match local HEAD after push\")",
].join(nl);

const NEW = [
  "    if slug:",
  "        # read the remote back, patiently: the commits API is eventually",
  "        # consistent for a few seconds after a push, and a single read turns a",
  "        # successful push into a reported failure.",
  "        attempts, after = 6, None",
  "        for i in range(attempts):",
  "            after = remote_head(slug, branch)",
  "            if after.get(\"sha\") == local_sha:",
  "                break",
  "            if i < attempts - 1:",
  "                time.sleep(2.0)",
  "        r.add(remote=slug, remote_branch=branch, remote_sha=(after or {}).get(\"sha\"),",
  "              matches=(after or {}).get(\"sha\") == local_sha,",
  "              readback_attempts=i + 1)",
  "        if (after or {}).get(\"sha\") != local_sha:",
  "            r.ok = False",
  "            r.errors.append(\"remote SHA does not match local HEAD after push\")",
].join(nl);

const hits = s.split(OLD).length - 1;
if (hits !== 1) throw new Error("anchor matched " + hits + "x");
if (!new RegExp("^import time$", "m").test(s)) {
  const anchor = "import subprocess" + nl;
  if (s.split(anchor).length - 1 !== 1) throw new Error("import anchor missing");
  s = s.replace(anchor, anchor + "import time" + nl);
}
copyFileSync(P, P + ".bak-readback");
writeFileSync(P, s.replace(OLD, NEW));
console.log("patched " + P);
