"""Single source of truth for ABRASAX paths.

Before this, Unity project paths were hardcoded in at least eight separate scripts:

    attach_floating_renderer_to_scene.py  SCENE  = r"C:\\UnityProjects\\..."
    probe_dll_literal.py                  DLL    = r"C:\\UnityProjects\\..."
    unity_status.py                       PROJ   = r"J:\\UnityProjects\\..."
    fix_unity_productname.py              PATH   = r"J:\\UnityProjects\\..."

Two roots (J: source of truth, C: build workspace) with the choice hardcoded per
script is exactly how a script silently operates on the wrong tree -- which nearly
happened tonight when a rebuild ran against a stale process.

Every script imports from here instead.

Roles, as established by DOC/UNITY-BUILD.md:
    J:\\UnityProjects\\ABRASAX-Brain   SOURCE OF TRUTH -- owns Packages/, ProjectSettings/
    C:\\UnityProjects\\ABRASAX-Brain   BUILD WORKSPACE -- owns Library/ (NVMe; the editor
                                      is on J: but J: is a USB HDD and Library is
                                      thousands of small files)

Use:
    from abra_paths import paths
    paths.unity_source          -> J:\\UnityProjects\\ABRASAX-Brain
    paths.unity_build           -> C:\\UnityProjects\\ABRASAX-Brain
    paths.unity_scene           -> <build>/Assets/Scenes/Main.unity
    paths.unity_dll             -> <build>/Library/ScriptAssemblies/Assembly-CSharp.dll
    paths.script(name)          -> C:\\ABRASAX\\SCRIPTS\\automation\\<name>

Environment overrides are honoured, so a moved tree needs no code edit:
    ABRASAX_ROOT, ABRASAX_UNITY_SOURCE, ABRASAX_UNITY_BUILD
"""
from __future__ import annotations

import os
from pathlib import Path



# A Unity project is recognised by its authoring files, not by where it lives.
UNITY_CANDIDATES = (
    r"J:\UnityProjects\ABRASAX-Brain",   # historical source drive
    r"G:\UnityProjects\ABRASAX-Brain",   # where it actually is on 2026-11-01
    r"C:\UnityProjects\ABRASAX-Brain",
    r"F:\UnityProjects\ABRASAX-Brain",
    r"E:\UnityProjects\ABRASAX-Brain",
    r"I:\UnityProjects\ABRASAX-Brain",
)
UNITY_BUILD_DEFAULT = r"C:\UnityProjects\ABRASAX-Brain"
DRIVE_LETTERS = "CDEFGHIJK"       # letters this host may carry


def _looks_like_unity_project(p: Path) -> bool:
    return (p / "Packages" / "manifest.json").is_file() and (p / "Assets").is_dir()


def discover_unity_source(explicit: str | None = None) -> Path:
    """Find the Unity source tree without assuming a drive letter.

    Order: explicit argument, ABRASAX_UNITY_SOURCE, known candidates, then a
    shallow scan of the letters this host has. An explicit/env path is honoured
    even if missing -- callers ask `.exists()` and get the truth.
    """
    if explicit:
        return Path(explicit)
    env = os.environ.get("ABRASAX_UNITY_SOURCE")
    if env:
        return Path(env)
    for cand in UNITY_CANDIDATES:
        if _looks_like_unity_project(Path(cand)):
            return Path(cand)
    for letter in DRIVE_LETTERS:
        cand = Path("%s:\\UnityProjects\\ABRASAX-Brain" % letter)
        if _looks_like_unity_project(cand):
            return cand
    return Path(UNITY_CANDIDATES[0])


def discover_unity_build(explicit: str | None = None,
                         source: Path | None = None) -> Path:
    """The workspace that owns Library/ (build products), else the C: default."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("ABRASAX_UNITY_BUILD")
    if env:
        return Path(env)
    for cand in UNITY_CANDIDATES:
        p = Path(cand)
        if (p / "Library").is_dir():
            return p
    return Path(UNITY_BUILD_DEFAULT)


class AbraPaths:
    """Resolved paths for this host. Immutable once constructed."""

    def __init__(self, root: str | None = None,
                 unity_source: str | None = None,
                 unity_build: str | None = None):
        self.root = Path(root or os.environ.get("ABRASAX_ROOT") or r"C:\ABRASAX")

        self.unity_source = discover_unity_source(unity_source)

        self.unity_build = discover_unity_build(unity_build, self.unity_source)

    # ---- ABRASAX tree ----------------------------------------------------
    @property
    def scripts(self) -> Path:
        return self.root / "SCRIPTS"

    @property
    def automation(self) -> Path:
        return self.scripts / "automation"

    @property
    def package(self) -> Path:
        return self.root / "abrasax"

    @property
    def tests(self) -> Path:
        # The suite lives in tests/. tests/python was aspirational and never
        # existed, so the path report read "MISS tests" while pytest was green.
        for cand in (self.root / "TESTS" / "python", self.root / "TESTS",
                     self.root / "tests"):
            if cand.is_dir():
                return cand
        return self.root / "TESTS"

    @property
    def docs(self) -> Path:
        return self.root / "DOC"

    @property
    def logs(self) -> Path:
        return self.root / "LOGS"

    @property
    def engine(self) -> Path:
        return self.root / "ENGINE"

    @property
    def floating_brain(self) -> Path:
        return self.engine / "floating_brain"

    @property
    def fb_bin(self) -> Path:
        return self.floating_brain / "cuda" / "bin"

    # ---- Unity -----------------------------------------------------------
    # Authoring paths live in the SOURCE tree (J:).
    @property
    def unity_assets(self) -> Path:
        return self.unity_source / "Assets"

    @property
    def unity_scripts(self) -> Path:
        return self.unity_assets / "BrainUI" / "Scripts"

    @property
    def unity_packages(self) -> Path:
        return self.unity_source / "Packages"

    @property
    def unity_settings(self) -> Path:
        return self.unity_source / "ProjectSettings"

    @property
    def unity_manifest(self) -> Path:
        return self.unity_packages / "manifest.json"

    @property
    def unity_editor_version(self) -> Path:
        return self.unity_settings / "ProjectVersion.txt"

    # Build outputs live in the BUILD tree (C:).
    @property
    def unity_library(self) -> Path:
        return self.unity_build / "Library"

    @property
    def unity_dll(self) -> Path:
        return self.unity_library / "ScriptAssemblies" / "Assembly-CSharp.dll"

    @property
    def unity_package_cache(self) -> Path:
        return self.unity_library / "PackageCache"

    @property
    def unity_build_assets(self) -> Path:
        return self.unity_build / "Assets"

    @property
    def unity_scene(self) -> Path:
        """The scene is authored in SOURCE but compiled in BUILD.

        Return the build copy when it exists (that is what the editor opened), else
        the source copy.
        """
        b = self.unity_build_assets / "Scenes" / "Main.unity"
        if b.exists():
            return b
        return self.unity_assets / "Scenes" / "Main.unity"

    @property
    def unity_scene_source(self) -> Path:
        return self.unity_assets / "Scenes" / "Main.unity"

    def script(self, name: str) -> Path:
        return self.automation / name

    # ---- services --------------------------------------------------------
    @property
    def renderer_url(self) -> str:
        return os.environ.get("ABRASAX_RENDER_URL", "http://127.0.0.1:9700")

    @property
    def brain_url(self) -> str:
        return os.environ.get("ABRASAX_BRAIN_URL", "http://127.0.0.1:9626")

    @property
    def gateway_url(self) -> str:
        return os.environ.get("ABRASAX_GATEWAY_URL", "http://127.0.0.1:9001")

    # ---- diagnostics -----------------------------------------------------
    def report(self) -> dict:
        """Existence of every path this system depends on."""
        checks = {
            "root": self.root,
            "scripts": self.scripts,
            "automation": self.automation,
            "package": self.package,
            "tests": self.tests,
            "docs": self.docs,
            "logs": self.logs,
            "floating_brain": self.floating_brain,
            "fb_bin": self.fb_bin,
            "unity_source": self.unity_source,
            "unity_build": self.unity_build,
            "unity_assets": self.unity_assets,
            "unity_scripts": self.unity_scripts,
            "unity_manifest": self.unity_manifest,
            "unity_library": self.unity_library,
            "unity_dll": self.unity_dll,
        }
        return {k: {"path": str(v), "exists": Path(v).exists()}
                for k, v in checks.items()}


paths = AbraPaths()

__all__ = ["AbraPaths", "paths"]
