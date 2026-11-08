// helpers/patch_repo_token_env.mjs — the one-shot credential helper read
// $ABX_GIT_TOKEN, but nothing ever exported it: _push_env() built an env dict
// that run() ignores. So the helper answered username=x-access-token with an
// EMPTY password and every push fell back to what the auth prompt could find —
// which is why the build worked in a terminal and hung under a redirect.
import { readFileSync, writeFileSync, copyFileSync } from "node:fs";

const P = "C:/ABRASAX/tools/abx/repo.py";
let s = readFileSync(P, "utf8");
if (s.includes('os.environ["ABX_GIT_TOKEN"] = tok')) { console.log("already patched"); process.exit(0); }
const nl = s.includes("\r\n") ? "\r\n" : "\n";
const OLD = ['    tok = token()',
             '    if tok:',
             '        # one-shot in-memory credential helper: prints the token to git only'].join(nl);
const NEW = ['    tok = token()',
             '    if tok:',
             '        # the helper below reads this from the child env; run() inherits os.environ',
             '        os.environ["ABX_GIT_TOKEN"] = tok',
             '        # one-shot in-memory credential helper: prints the token to git only'].join(nl);
const hits = s.split(OLD).length - 1;
if (hits !== 1) throw new Error("anchor matched " + hits + "x");
copyFileSync(P, P + ".bak-tokenenv");
writeFileSync(P, s.replace(OLD, NEW));
console.log("patched " + P);
