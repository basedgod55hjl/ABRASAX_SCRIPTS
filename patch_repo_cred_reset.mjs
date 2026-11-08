// helpers/patch_repo_cred_reset.mjs — stop `git push` from hanging on a
// credential prompt.
// Incident: rebuild_repos.py --go deleted 20 repos, recreated 2, then froze on
// `git credential fill` -> Git Credential Manager waiting for a terminal that
// does not exist. `-c credential.helper=X` APPENDS to the inherited helper list,
// it does not replace it, so GCM still ran. The fix is to reset the list first
// (`-c credential.helper=`) and to forbid terminal prompting outright.
// Handles CRLF: the repo checks out with \r\n, so anchors are built with the
// file's own newline.
import { readFileSync, writeFileSync, copyFileSync } from "node:fs";

const P = "C:/ABRASAX/tools/abx/repo.py";
let s = readFileSync(P, "utf8");
if (s.includes("GCM_INTERACTIVE")) { console.log("already patched"); process.exit(0); }

const nl = s.includes("\r\n") ? "\r\n" : "\n";
const OLD = [
  'def _push(tree: Path, remote: str, refspec: str, timeout: float = 1800.0) -> dict[str, Any]:',
  '    """Push without ever writing the token into .git/config or a URL on disk."""',
  '    tok = token()',
  '    if tok:',
  '        # one-shot in-memory credential helper: prints the token to git only',
  '        helper = "!f() { echo username=x-access-token; echo password=$ABX_GIT_TOKEN; }; f"',
  '        cmd = ["git", "-c", f"credential.helper={helper}", "push", remote, refspec]',
  '        return run(cmd, cwd=tree, timeout=timeout)',
  '    return run(["git", "push", remote, refspec], cwd=tree, timeout=timeout)',
].join(nl);

const NEW = [
  'def _push(tree: Path, remote: str, refspec: str, timeout: float = 1800.0) -> dict[str, Any]:',
  '    """Push without ever writing the token into .git/config or a URL on disk.',
  '',
  '    Two things keep this from hanging forever, which it did once: an empty',
  '    `credential.helper=` resets the inherited helper list (Git Credential',
  '    Manager otherwise runs *in addition* to the one-shot helper and blocks on a',
  '    terminal that does not exist), and GIT_TERMINAL_PROMPT=0 turns any remaining',
  '    prompt into an error instead of a wait.',
  '    """',
  '    os.environ["GIT_TERMINAL_PROMPT"] = "0"',
  '    os.environ["GCM_INTERACTIVE"] = "never"',
  '    tok = token()',
  '    if tok:',
  '        # one-shot in-memory credential helper: prints the token to git only',
  '        helper = "!f() { echo username=x-access-token; echo password=$ABX_GIT_TOKEN; }; f"',
  '        cmd = ["git", "-c", "credential.helper=", "-c", f"credential.helper={helper}",',
  '               "push", remote, refspec]',
  '        return run(cmd, cwd=tree, timeout=timeout)',
  '    return run(["git", "-c", "credential.helper=", "push", remote, refspec], cwd=tree, timeout=timeout)',
].join(nl);

const hits = s.split(OLD).length - 1;
if (hits !== 1) throw new Error("anchor matched " + hits + "x");
copyFileSync(P, P + ".bak-credreset");
writeFileSync(P, s.replace(OLD, NEW));
console.log("patched " + P);
