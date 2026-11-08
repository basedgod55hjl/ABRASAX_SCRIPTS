import io, os, shutil

P = r"C:\ABRASAX\abrasax\gateway.py"
src = io.open(P, encoding="utf-8").read()

OLD = '''        owners = _model_owners()
        owner = owners.get(model)
        if owner is None and model in owners.values():
            owner = model
        if owner and owner != "auto":
            return owner, model
'''

NEW = '''        owners = _model_owners()
        owner = owners.get(model)
        if owner is None and model in owners.values():
            # The model id IS a provider name ("deepseek").  Measured
            # 2026-11-01: pinning route=deepseek but still sending model
            # "deepseek" upstream failed 400 "Model Not Exist" - a provider
            # name is a route, not a model id, so use that provider's default.
            return model, _provider_default_model(model)
        if owner and owner != "auto":
            return owner, model
'''

if OLD not in src:
    raise SystemExit("ANCHOR NOT FOUND")
if "_provider_default_model" in src:
    raise SystemExit("already patched")

HELPER = '''def _provider_default_model(name: str) -> str | None:
    """The default model id a provider declares in providers.json."""
    try:
        with open(ROOT / "CONFIG" / "llm" / "providers.json", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    conf = (data.get("providers") or data or {}).get(name) or {}
    models = conf.get("models") or {}
    if isinstance(models, dict):
        d = models.get("default")
        return d if isinstance(d, str) and d else None
    if isinstance(models, list) and models:
        return models[0] if isinstance(models[0], str) else None
    return None


'''

src = src.replace(OLD, NEW, 1)
src = src.replace("_MODEL_OWNER_CACHE: dict[str, str] = {}",
                  HELPER + "_MODEL_OWNER_CACHE: dict[str, str] = {}", 1)

bak = P + ".bak-routefix2"
if not os.path.exists(bak):
    shutil.copy2(P, bak)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched", P, os.path.getsize(P), "bytes")
