#!/usr/bin/env python
"""ABRASAX UI BRAIN builder (v2).

The skill corpus has TWO forms on disk, and a brain that reads only one of them
is wrong by omission:
  A. directory skills  -- <skill>/SKILL.md          (526 found)
  B. flat skill files  -- <dir>/<skill>.md with YAML front matter containing
                          name+description            (e.g. abrasax_skills/*.md)

Everything else (template libraries, reference sheets, per-layout docs) is an
asset of a skill, not a skill, and is counted as such instead of being
inflated into the index.

Ranks by *evidence*: domain weight x evidence class + stack relevance, where
stack relevance means "this skill targets a technology the ABRASAX overlay is
actually built on" (imgui/glfw/OpenGL/GLSL, Win32/DWM/D3D, or the web surface).

Outputs DATA/runtime-memory/ui_brain.{json,md}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\ABRASAX")
SKILL_ROOTS = [
    ROOT / "AGENTS/SKILLS/source-skills",
    ROOT / "AGENTS/SKILLS/rust-skills",
]
FB = ROOT / "ENGINE/floating_brain"
OUT_JSON = ROOT / "DATA/runtime-memory/ui_brain.json"
OUT_MD = ROOT / "DATA/runtime-memory/ui_brain.md"
PRUNE = {"node_modules", ".git", ".gradle", "__pycache__", "target", "dist"}

# ---------------------------------------------------------------- domains
DOMAINS = {
    "design-taste": 9,
    "web-frontend": 7,
    "native-desktop": 10,
    "gpu-render": 12,
    "hologram-panel": 12,
    "data-viz": 6,
    "mobile-ui": 3,
    "agent-ui": 6,
}
DOMAIN_RX = {
    "design-taste": r"design|aesthetic|typograph|colou?r|brand|theme|visual|\bux\b|layout|spacing",
    "web-frontend": r"frontend|front-end|\breact\b|next\.?js|tailwind|\bcss\b|\bhtml\b|svelte|\bvue\b|shadcn",
    "native-desktop": r"\bwin32\b|winui|\bdwm\b|mica|acrylic|direct3d|\bd3d\w*|dxgi|\bwpf\b|\bmaui\b|desktop app|window",
    "gpu-render": r"shader|glsl|opengl|\bglfw\b|imgui|dear.?pygui|\bp5\.?js\b|webgl|cuda|vulkan|fbo|framebuffer",
    "hologram-panel": r"holograph|overlay|floating brain|orbital|\bhud\b|scanline|emissive",
    "data-viz": r"dashboard|chart|infographic|visuali[sz]|data app|diagram|plot|telemetry",
    "mobile-ui": r"flutter|android|\bios\b|swiftui|jetpack|responsive",
    "agent-ui": r"mcp app|widget|artifact|agent ui|computer.?use|chat ui|command window",
}
DOMAIN_RX = {k: re.compile(v, re.I) for k, v in DOMAIN_RX.items()}

# Technology the live UI is built on -> weight. Matched on word boundaries so
# "html" doesn't fire inside "…", and "d3d" doesn't fire on "dragon".
STACK = {
    "imgui": 20, "opengl": 18, "glfw": 16, "glsl": 16, "dearpygui": 14,
    "win32": 14, "dwm": 12, "winui": 12, "d3d": 14, "dxgi": 12,
    "p5js": 10, "shader": 8, "maui": 4, "flutter": 4,
    "shadcn": 4, "react": 3, "tailwind": 3, "html": 2,
}
STACK_RX = {
    "d3d": re.compile(r"\bd3d\d*\b", re.I),
    "p5js": re.compile(r"\bp5\.?js\b", re.I),
    "glsl": re.compile(r"\bglsl\b", re.I),
    "opengl": re.compile(r"\bopengl\b|\bGL_\w+", re.I),
    "imgui": re.compile(r"\bimgui\b|dear\s?imgui", re.I),
    "dearpygui": re.compile(r"dear\s?pygui", re.I),
    "glfw": re.compile(r"\bglfw\w*\b", re.I),
    "win32": re.compile(r"\bwin32\b|\buser32\b|\bhwnd\b", re.I),
    "dwm": re.compile(r"\bdwm\w*\b", re.I),
    "winui": re.compile(r"\bwinui\b", re.I),
    "dxgi": re.compile(r"\bdxgi\w*\b", re.I),
    "shader": re.compile(r"\bshaders?\b", re.I),
    "maui": re.compile(r"\bmaui\b", re.I),
    "flutter": re.compile(r"\bflutter\b", re.I),
    "shadcn": re.compile(r"\bshadcn\b", re.I),
    "react": re.compile(r"\breact\b", re.I),
    "tailwind": re.compile(r"\btailwind\b", re.I),
    "html": re.compile(r"\bhtml\b", re.I),
}

FAMILY_RX = [
    re.compile(r"^7d[- ]crystal", re.I),
    re.compile(r"^swarm[-_ ](entanglement|learning|report|suggestion|analy|analyzer|diagnost)", re.I),
    re.compile(r"^swarm[-_ ](agent|code|conscience|intelligence|performance|upgrade|ts)", re.I),
    re.compile(r"^(abort|ts-.*abort|type.*abort|node.*abort)", re.I),
    re.compile(r"^(claude ?code|claudesign|claudette)", re.I),
    re.compile(r"^imgui-", re.I),
    re.compile(r"^sparc", re.I),
    re.compile(r"^(release|deploy|production)", re.I),
    re.compile(r"^(memory|memory-|memory_).*", re.I),
    re.compile(r"^(perf|performance)", re.I),
    re.compile(r"^(swarm-)?(status|monitor)", re.I),
    re.compile(r"^(pr|pull-request)", re.I),
]
PENALTY_RX = re.compile(r"\b(deprecated|stub|placeholder|unused)\b", re.I)

# Credentials must never ride along with a skill description into an agent
# prompt. Redact at build time and count it.
REDACT_RX = re.compile(
    r"github_pat_[A-Za-z0-9_]{20,}"
    r"|gh[pousr]_[A-Za-z0-9]{30,}"
    r"|sk-[A-Za-z0-9\-]{20,}"
    r"|hf_[A-Za-z0-9]{24,}"
    r"|xox[baprs]-[A-Za-z0-9\-]{10,}"
    r"|[A-Fa-f0-9]{32,}"
)


def redact(text: str) -> tuple[str, int]:
    return REDACT_RX.subn("[REDACTED]", text)



def family_of(name: str) -> str:
    for rx in FAMILY_RX:
        if rx.search(name):
            return rx.pattern
    return name.strip().lower()


def front_matter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out: dict = {}
    key = None
    for raw in text[3:end].splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw)
        if m:
            key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
            out[key] = val
        elif key and raw[:1] in (" ", "\t"):
            out[key] = (out.get(key, "") + " " + raw.strip()).strip()
    return out


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def domains_in(text: str) -> list[str]:
    return [d for d, rx in DOMAIN_RX.items() if rx.search(text)]


def stack_in(text: str) -> tuple[int, list[str]]:
    total, hit = 0, []
    for tok, rx in STACK_RX.items():
        if rx.search(text):
            total += STACK[tok]
            hit.append(tok)
    return total, hit


def classify(md_path: Path, text: str) -> dict | None:
    """Return a skill record, or None if this .md is an asset, not a skill."""
    fm = front_matter(text)
    if md_path.name != "SKILL.md":
        # Flat form: only counts as a skill with real front matter identity.
        if not (fm.get("name") and fm.get("description")):
            return None
        if len(fm.get("description", "")) < 12:
            return None
    name = fm.get("name") or md_path.parent.name
    raw_desc = re.sub(r"\s+", " ", fm.get("description") or "")[:300]
    desc, n_redacted = redact(raw_desc)
    body, n_body = redact(text[:6000])
    n_redacted += n_body
    blob = f"{name} {desc} {body}"
    doms = domains_in(blob)
    st_score, st_hits = stack_in(blob)
    base = sum(DOMAINS[d] for d in doms)
    title_boost = sum(
        DOMAINS[d] for d in doms if DOMAIN_RX[d].search(name)
    )
    if md_path.name == "SKILL.md":
        assets = sum(len(fns) for _, _, fns in os.walk(md_path.parent)) - 1
        evid = "dir"
    else:
        assets = 0
        evid = "flat"
    total = base + title_boost + st_score + min(6, max(0, assets))
    if not doms and st_score == 0:
        return None
    if PENALTY_RX.search(desc):
        total -= 8
    return {
        "name": name,
        "form": evid,
        "path": str(md_path),
        "file": md_path.name,
        "dir": md_path.parent.name,
        "bytes": md_path.stat().st_size,
        "assets": max(0, assets),
        "description": desc,
        "redacted": n_redacted,
        "domains": doms,
        "stack": st_hits,
        "score": total,
        "family": family_of(name),
    }


def scan() -> tuple[list[dict], dict]:
    skills: list[dict] = []
    stats = {"md_seen": 0, "dir_skills": 0, "flat_skills": 0, "assets": 0}
    for root in SKILL_ROOTS:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in PRUNE]
            for fn in filenames:
                if not fn.endswith(".md"):
                    continue
                p = Path(dirpath) / fn
                stats["md_seen"] += 1
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                rec = classify(p, text)
                if rec is None:
                    stats["assets"] += 1
                    continue
                stats["dir_skills" if fn == "SKILL.md" else "flat_skills"] += 1
                skills.append(rec)
    return skills, stats


def collapse(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        buckets.setdefault(r["family"], []).append(r)
    keep, dropped = [], []
    for group in buckets.values():
        group.sort(key=lambda r: (-r["score"], -r["bytes"]))
        top = group[0]
        top["aliases"] = sorted(g["name"] for g in group[1:])
        top["alias_paths"] = [g["path"] for g in group[1:]]
        keep.append(top)
        dropped.extend(group[1:])
    keep.sort(key=lambda r: (-r["score"], r["name"].lower()))
    return keep, dropped


def read_contract() -> dict:
    p = FB / "ABRAX_LAYER_CONTRACT.md"
    if not p.exists():
        return {"path": str(p), "present": False, "modules": [], "rules": []}
    text = p.read_text(encoding="utf-8", errors="replace")
    mods = re.findall(r"^### `([^`]+)` \(worker ([A-Z])\)", text, re.M)
    return {
        "path": str(p),
        "present": True,
        "sha16": sha(p),
        "bytes": p.stat().st_size,
        "modules": [{"file": f, "worker": w} for f, w in mods],
        "activity_schema": '"state": "idle|thinking|tool|memory|alert|high_load"' in text,
        "rules": [ln[2:].strip() for ln in text.splitlines() if ln.startswith("- ")][:24],
    }


def read_code() -> list[dict]:
    out = []
    for p in sorted(FB.glob("*.py")):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        classes = re.findall(r"^class (\w+)", text, re.M)
        funcs = re.findall(r"^(?:def|    def) (\w+)", text, re.M)
        pub = [f for f in funcs if not f.startswith("_")]
        out.append(
            {
                "file": p.name,
                "bytes": p.stat().st_size,
                "sha16": sha(p),
                "classes": classes[:24],
                "api": pub[:40],
                "public_api_count": len(pub),
            }
        )
    return out


REQUIRED_SDK = [
    "Include/10.0.26100.0/um/windows.h",
    "Include/10.0.26100.0/um/dwmapi.h",
    "Include/10.0.26100.0/um/d3d11.h",
    "Include/10.0.26100.0/um/dcomp.h",
    "Include/10.0.26100.0/shared/dxgi1_6.h",
    "Lib/10.0.26100.0/um/x64/d3d11.lib",
    "Lib/10.0.26100.0/um/x64/dwmapi.lib",
    "Lib/10.0.26100.0/um/x64/dxguid.lib",
    "bin/10.0.26100.0/x64/rc.exe",
    "bin/10.0.26100.0/x64/signtool.exe",
]


def read_sdk() -> dict:
    kits = Path(r"C:\Program Files (x86)\Windows Kits\10")
    ver = "10.0.26100.0"
    present = {c: (kits / c).exists() for c in REQUIRED_SDK}
    probe = ROOT / "SCRIPTS/sdkprobe/sdkcheck.exe"
    run = None
    if probe.exists():
        try:
            r = subprocess.run([str(probe)], capture_output=True, text=True, timeout=30)
            run = {"rc": r.returncode, "out": r.stdout.strip().splitlines()}
        except (OSError, subprocess.SubprocessError) as exc:
            run = {"rc": -1, "out": [f"probe failed: {exc}"]}
    return {
        "kits_root": str(kits),
        "sdk_version": ver,
        "required": present,
        "all_required_present": all(present.values()),
        "um_header_count": len(list((kits / "Include" / ver / "um").glob("*.h"))),
        "probe_exe": str(probe),
        "probe_sha16": sha(probe) if probe.exists() else None,
        "probe_run": run,
    }


def build() -> dict:
    rows, stats = scan()
    ui_rows = [r for r in rows if r["score"] >= 6]
    merged, dropped = collapse(ui_rows)
    dom_counts: dict[str, int] = {}
    stack_counts: dict[str, int] = {}
    for r in merged:
        for d in r["domains"]:
            dom_counts[d] = dom_counts.get(d, 0) + 1
        for s in r["stack"]:
            stack_counts[s] = stack_counts.get(s, 0) + 1
    brain = {
        "generator": "SCRIPTS/automation/build_ui_brain.py",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "primal_hex": "4f5349524953424c58434b",
        "corpus": {
            **stats,
            "skills_total": len(rows),
            "ui_relevant": len(ui_rows),
            "canonical": len(merged),
            "aliases_collapsed": len(dropped),
            "roots": [str(p) for p in SKILL_ROOTS],
        },
        "domains": dict(sorted(dom_counts.items(), key=lambda kv: -kv[1])),
        "stack": dict(sorted(stack_counts.items(), key=lambda kv: -kv[1])),
        "skills": merged,
        "aliases": sorted({d["name"] for d in dropped}),
        "contract": read_contract(),
        "code": read_code(),
        "sdk": read_sdk(),
    }
    brain["security"] = {
        "redaction_rule": "github_pat_/gh?_/sk-/hf_/xox/32+hex -> [REDACTED]",
        "skills_with_redactions": sum(1 for s in merged if s.get("redacted")),
        "total_redactions": sum(s.get("redacted", 0) for s in merged),
    }
    brain["digest"] = hashlib.sha256(
        json.dumps(brain["skills"], sort_keys=True).encode()
    ).hexdigest()[:16]
    return brain


def render_md(b: dict) -> str:
    c = b["corpus"]
    L = ["# ABRASAX UI BRAIN", ""]
    L.append(f"generated `{b['generated_at']}` · digest `{b['digest']}`")
    L.append("")
    L.append(
        f"{c['md_seen']} markdown files scanned → {c['dir_skills']} directory skills + "
        f"{c['flat_skills']} flat skills → **{c['ui_relevant']} UI-relevant** → "
        f"**{c['canonical']} canonical** ({c['aliases_collapsed']} aliases collapsed, "
        f"{c['assets']} assets treated as assets)."
    )
    L += ["", "## Where the weight is", "", "| domain | skills |", "|---|---|"]
    L += [f"| {d} | {n} |" for d, n in b["domains"].items()]
    L += ["", "| stack the UI runs on | skills referencing it |", "|---|---|"]
    L += [f"| {s} | {n} |" for s, n in b["stack"].items()]
    L += ["", "## Ranked UI skills", "",
          "| score | skill | form | domains | stack | what it gives the build |",
          "|---|---|---|---|---|---|"]
    for r in b["skills"]:
        desc = r["description"].replace("|", "/")[:130]
        L.append(
            f"| {r['score']} | `{r['name']}` | {r['form']} | {', '.join(r['domains'])} | "
            f"{','.join(r['stack'])[:24]} | {desc} |"
        )
    s = b["sdk"]
    L += ["", "## Windows SDK", "",
          f"`{s['kits_root']}` **{s['sdk_version']}**, {s['um_header_count']} um headers, "
          f"all required present: **{s['all_required_present']}**", ""]
    if s["probe_run"]:
        L += ["```", *s["probe_run"]["out"], "```"]
    con = b["contract"]
    L += ["", "## Build contract", ""]
    if con["present"]:
        L.append(f"`{con['path']}` ({con['bytes']} B, sha16 `{con['sha16']}`) · "
                 f"activity schema ok: {con['activity_schema']}")
        for m in con["modules"]:
            L.append(f"- worker {m['worker']} → `{m['file']}`")
    L += ["", "## Live UI code", "", "| file | bytes | classes | public API |", "|---|---|---|---|"]
    for f in b["code"]:
        L.append(f"| `{f['file']}` | {f['bytes']} | {', '.join(f['classes'][:5])} | {f['public_api_count']} |")
    return "\n".join(L) + "\n"


def main() -> int:
    b = build()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(b, indent=1), encoding="utf-8")
    OUT_MD.write_text(render_md(b), encoding="utf-8")
    c = b["corpus"]
    print(f"UI brain -> {OUT_JSON} ({OUT_JSON.stat().st_size} B)")
    print(f"  md={c['md_seen']} dir_skills={c['dir_skills']} flat_skills={c['flat_skills']} "
          f"assets={c['assets']}")
    print(f"  ui_relevant={c['ui_relevant']} canonical={c['canonical']} "
          f"aliases={c['aliases_collapsed']} digest={b['digest']}")
    print(f"  sdk_all_present={b['sdk']['all_required_present']} "
          f"probe_rc={(b['sdk']['probe_run'] or {}).get('rc')}")
    for r in b["skills"][:15]:
        print(f"   {r['score']:>4} {r['form']:5} {r['name'][:36]:36} {','.join(r['stack'])[:40]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
