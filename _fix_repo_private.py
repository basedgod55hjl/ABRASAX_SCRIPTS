import io
import ast

p = r"C:\abrasax\tools\abx\repo.py"
s = io.open(p, encoding="utf-8").read()

old = s[s.index("def remote_repos(owner: str = OWNER_DEFAULT)"):s.index("def remote_head(")]
new = '''def remote_repos(owner: str = OWNER_DEFAULT) -> dict[str, Any]:
    """Every repo the authenticated user can see *and* owns.

    Two sources are merged because the public listing hides private repos:
      * /users/{owner}/repos  -> public repos
      * /user/repos           -> everything the token can read (incl. private)
    """
    tok = token()
    if not tok:
        return {"ok": False, "error": "no github token", "repos": {}}
    out: dict[str, Any] = {}
    errors: list[str] = []

    def _record(repo: dict[str, Any]) -> None:
        own = (repo.get("owner") or {}).get("login")
        if own and own != owner:
            return
        out[repo["name"]] = {
            "full_name": repo["full_name"],
            "private": repo["private"],
            "branch": repo.get("default_branch"),
            "pushed_at": repo.get("pushed_at"),
            "size_kb": repo.get("size"),
            "archived": repo.get("archived"),
            "html_url": repo.get("html_url"),
        }

    for path in (f"/users/{owner}/repos?per_page=100&type=owner", "/user/repos?per_page=100&affiliation=owner"):
        page = 1
        while True:
            sep = "&" if "?" in path else "?"
            res = _api(f"{path}{sep}page={page}")
            if not res["ok"]:
                errors.append(f"{path}: {res.get('error')}")
                break
            batch = res["body"]
            if not batch:
                break
            for repo in batch:
                _record(repo)
            if len(batch) < 100:
                break
            page += 1

    return {"ok": bool(out), "repos": out, "count": len(out), "errors": errors}


'''
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
ast.parse(s)
print("remote_repos now merges public + private")
