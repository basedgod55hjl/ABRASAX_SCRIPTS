import io, os, shutil

P = r"C:\ABRASAX\abrasax\gateway.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''def _pick_route(payload: dict) -> tuple[str, str | None]:
    model = str(payload.get("model") or "").strip()
    for route in ("lmstudio", "nvidia", "xpl"):
        if model.startswith(route + ":"):
            return route, model.split(":", 1)[1] or None
    extra = payload.get("abrasax") or {}
    route = str(extra.get("route") or "auto")
'''

NEW = '''_MODEL_OWNER_CACHE: dict[str, str] = {}


def _model_owners() -> dict[str, str]:
    """Map model id -> provider name, from providers.json.

    Cached; the config is read at most once per process on the chat path.
    """
    if _MODEL_OWNER_CACHE:
        return _MODEL_OWNER_CACHE
    try:
        with open(ROOT / "CONFIG" / "llm" / "providers.json", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return _MODEL_OWNER_CACHE
    for name, conf in (data.get("providers") or data or {}).items():
        if not isinstance(conf, dict):
            continue
        models = conf.get("models") or {}
        if isinstance(models, dict):
            ids = [models.get("default")]
            ids.extend((models.get("aliases") or {}).keys())
            ids.extend((models.get("aliases") or {}).values())
        elif isinstance(models, list):
            ids = list(models)
        else:
            ids = []
        for mid in ids:
            if isinstance(mid, str) and mid.strip():
                _MODEL_OWNER_CACHE.setdefault(mid.strip(), name)
    return _MODEL_OWNER_CACHE


def _pick_route(payload: dict) -> tuple[str, str | None]:
    model = str(payload.get("model") or "").strip()
    for route in ("lmstudio", "nvidia", "xpl"):
        if model.startswith(route + ":"):
            return route, model.split(":", 1)[1] or None
    extra = payload.get("abrasax") or {}
    route = str(extra.get("route") or "auto")

    # Measured 2026-11-01: posting model="deepseek" returned 502 - _pick_route
    # yielded ("auto", "deepseek"), so "deepseek" was pushed downstream as a
    # MODEL id and the auto chain tried lmstudio/nvidia first ("all providers
    # failed").  A model id that a provider declares - or that IS the provider
    # name - must pin that provider, not fall through to auto.
    if model and route == "auto" and model not in {"auto", "abrasax/auto"}:
        owners = _model_owners()
        owner = owners.get(model)
        if owner is None and model in owners.values():
            owner = model
        if owner and owner != "auto":
            return owner, model
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND - refusing to patch")
if "_model_owners" in src:
    raise SystemExit("already patched")

src = src.replace(OLD, NEW, 1)

# json/ROOT must be available at that point in the module.
for need, imp in (("import json", "import json\n"),):
    if need not in src.split("def _pick_route")[0]:
        raise SystemExit("missing %r before _pick_route - inspect manually" % need)
if "\nROOT =" not in src:
    print("WARN: ROOT not defined at module level - checking import")

bak = P + ".bak-routefix"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P, os.path.getsize(P), "bytes; backup", bak)
