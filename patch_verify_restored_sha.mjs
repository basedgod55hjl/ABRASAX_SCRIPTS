// helpers/patch_verify_restored_sha.mjs — `git rev-parse <missing ref>` prints
// the ref name and exits non-zero, so an empty mirror yielded mirror_head =
// "refs/heads/main" (truthy) instead of None, and the empty-repo branch never
// ran. Only a 40-hex string counts as a HEAD.
import { readFileSync, writeFileSync, copyFileSync } from "node:fs";

const P = "C:/ABRASAX/SCRIPTS/verify_restored.py";
let s = readFileSync(P, "utf8");
if (s.includes("_sha(")) { console.log("already patched"); process.exit(0); }
const nl = s.includes("\r\n") ? "\r\n" : "\n";

const OLD_HELPERS = "def main(argv: list[str] | None = None) -> int:";
const NEW_HELPERS = [
  "def _sha(value: str | None) -> str | None:",
  '    """A real object id, or None. rev-parse echoes the ref name when it cannot resolve."""',
  "    v = (value or \"\").strip()",
  "    return v if len(v) == 40 and all(c in \"0123456789abcdef\" for c in v.lower()) else None",
  "",
  "",
  "def main(argv: list[str] | None = None) -> int:",
].join(nl);

const OLD_TREE = '        mirror_tree = m["stdout"].strip() or None';
const NEW_TREE = '        mirror_tree = _sha(m["stdout"])';
const OLD_HEAD = '        mirror_head = m_head["stdout"].strip() or None';
const NEW_HEAD = '        mirror_head = _sha(m_head["stdout"])';

for (const [from, to] of [[OLD_HELPERS, NEW_HELPERS], [OLD_TREE, NEW_TREE], [OLD_HEAD, NEW_HEAD]]) {
  const hits = s.split(from).length - 1;
  if (hits !== 1) throw new Error("anchor matched " + hits + "x: " + from.slice(0, 50));
  s = s.replace(from, to);
}
copyFileSync(P, P + ".bak-sha");
writeFileSync(P, s);
console.log("patched " + P);
