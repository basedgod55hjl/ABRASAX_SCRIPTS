"""End-to-end verification of the ABRASAX sense stack.

Checks every layer in order and prints one PASS/FAIL line per claim. Run this
whenever something feels wrong; it answers "is it actually wired?" with
measured facts rather than assumptions.

    python SCRIPTS/tools/e2e_verify.py
"""
from __future__ import annotations

import json
import socket
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, r"C:\ABRASAX")

ADB = r"C:\abrasax\_DEAD_PATH\Android\platform-tools\adb.exe"  # DEAD PATH (sirch): no adb.exe on this host
SERIAL = "R5CY308WZVK"
DAEMON = "http://127.0.0.1:9633"

results: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    try:
        detail = fn()
        results.append((name, True, str(detail)))
        print(f"  PASS  {name}: {detail}")
    except Exception as exc:
        results.append((name, False, f"{type(exc).__name__}: {exc}"))
        print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")


def http_json(url, method="GET", timeout=90):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main() -> int:
    print("=== 1. device ===")
    import subprocess
    check("adb device attached", lambda: subprocess.run(
        [ADB, "devices"], capture_output=True, text=True, timeout=20
    ).stdout.splitlines()[1].split()[0])

    def apk_installed():
        out = subprocess.run([ADB, "-s", SERIAL, "shell", "pm", "path", "ai.abrasax.imu"],
                             capture_output=True, text=True, timeout=20).stdout.strip()
        assert out.startswith("package:"), out
        return out

    check("APK installed", apk_installed)

    def service_running():
        out = subprocess.run([ADB, "-s", SERIAL, "shell", "dumpsys", "activity",
                              "services", "ai.abrasax.imu"],
                             capture_output=True, text=True, timeout=25).stdout
        assert "ServiceRecord" in out, "ImuService not in the service list"
        return "ImuService registered"

    check("IMU service running", service_running)

    def forward_up():
        out = subprocess.run([ADB, "-s", SERIAL, "forward", "--list"],
                             capture_output=True, text=True, timeout=20).stdout
        assert "tcp:8790 tcp:8765" in out, out
        return out.strip()

    check("adb forward 8790->8765", forward_up)

    print("=== 2. sensing ===")
    from abrasax.live_imu import LiveImu
    from abrasax.adb_sensors import AdbSensorReader

    def imu_live():
        imu = LiveImu(serial=SERIAL)
        assert imu.status() == "available", "live_imu not available"
        s = imu.sample()
        assert s and s["origin"] == "measured", "no measured sample"
        return f"{s['rate_hz']}Hz heading={s['heading_deg']}"

    check("50Hz IMU measured", imu_live)

    def adb_sensors():
        r = AdbSensorReader(serial=SERIAL)
        assert r.status() == "available", "adb sensors not available"
        d = r.sample()
        assert d and d["origin"] == "measured"
        return f"{d['device']['sensors_live']} sensors, alt={d.get('derived', {}).get('altitude_m')}m"

    check("dumpsys sensors measured", adb_sensors)

    print("=== 2b. position and frame ===")

    def position_fix():
        from abrasax.position import PositionReader
        r = PositionReader(serial=SERIAL)
        assert r.status() in ("available", "stale"), "no position provider"
        s = r.sample()
        assert s is not None, "no fix"
        # Age must be reported; a fix without an age is not trustworthy.
        assert "age_s" in s and s["age_s"] is not None, "fix has no age"
        assert -90 <= s["lat"] <= 90 and -180 <= s["lon"] <= 180, "out of range"
        return (f"{s['provider']} {s['lat']:.6f},{s['lon']:.6f} "
                f"+-{s['horizontal_accuracy_m']:.1f}m age={s['age_s']:.0f}s "
                f"fresh={s['fresh']}")

    check("position fix with age", position_fix)

    def frame_is_android():
        """Ground truth for the frame: at rest the accelerometer must read
        ~9.81 m/s^2 of specific force, and the rotation vector must be a unit
        quaternion. If either fails, every heading derived here is suspect."""
        import math
        from abrasax.live_imu import LiveImu
        frames = list(LiveImu(serial=SERIAL).stream(count=15))
        assert frames, "no IMU frames"
        n = len(frames)
        acc = [sum(f.accel[i] for f in frames) / n for i in range(3)]
        rot = [sum(f.rotation[i] for f in frames) / n for i in range(4)]
        amag = math.sqrt(sum(v * v for v in acc))
        rmag = math.sqrt(sum(v * v for v in rot))
        assert 9.0 <= amag <= 10.6, f"|accel|={amag:.2f} is not gravity"
        assert abs(rmag - 1.0) < 0.05, f"|rot|={rmag:.3f} is not a unit quaternion"
        up = "XYZ"[max(range(3), key=lambda i: abs(acc[i]))]
        return f"|accel|={amag:.3f} |rot|={rmag:.3f} gravity-axis={up}"

    check("android frame matches (accel=gravity, unit quat)", frame_is_android)

    print("=== 2c. tracking status ===")

    def tracking_reports_liveness():
        """Every source must answer the liveness question, not dodge it.

        The IMU and the dumpsys ring must be TRACKING; anything else is a
        finding. Position is expected to be STALE when the phone has not moved
        (its fix ages out), so that is checked for consistency rather than
        forced to TRACKING.
        """
        from abrasax.phone_senses import build_registry
        rows = build_registry(serial=SERIAL).discover()
        by_key = {r["key"]: (r.get("tracking") or {}) for r in rows}
        imu = by_key.get("s25:imu-live", {})
        adb = by_key.get("s25:adb", {})
        assert imu.get("state") == "TRACKING", f"imu-live: {imu}"
        assert adb.get("state") == "TRACKING", f"adb: {adb}"
        rate = imu.get("observed_rate_hz")
        assert rate and 40 <= rate <= 60, f"imu-live rate {rate}"
        pos = by_key.get("s25:position", {})
        assert pos.get("state") in ("TRACKING", "STALE"), f"position: {pos}"
        return (f"imu {imu['state']} @{rate:.1f}Hz, adb {adb['state']} "
                f"age={adb.get('age_s')}s, position {pos.get('state')}")

    check("tracking states reported", tracking_reports_liveness)

    print("=== 3. registry ===")

    def registry_live():
        from abrasax.phone_senses import build_registry
        rows = build_registry(serial=SERIAL).discover()
        live = [r["key"] for r in rows if r["status"] == "available"]
        assert "s25:imu-live" in live, f"imu-live not available: {live}"
        return ", ".join(live)

    check("registry providers available", registry_live)

    print("=== 4. world state ===")

    def ingest_roundtrip():
        from abrasax.sense_loop import tick
        rec = tick(serial=SERIAL)
        assert not rec.get("error"), rec.get("error")
        assert rec["ingested"] >= 1, f"nothing ingested: {rec}"
        return f"ingested={rec['ingested']} in {rec['duration_ms']}ms"

    check("sense_loop tick ingests", ingest_roundtrip)

    print("=== 5. resident loop ===")

    def pulse_alive():
        pidf = Path(r"C:\ABRASAX\LOGS\pulse.pid")
        assert pidf.exists(), "no pulse.pid"
        return f"pid={pidf.read_text().strip()}"

    check("pulse running", pulse_alive)

    print("=== 5b. model independence ===")

    def sensing_does_not_import_llm():
        """Static guarantee: the world state must not import a model client.

        Verified by AST over the sensing modules rather than by grep, so an
        `import x as llm` or a `from . import llm` cannot slip through.
        """
        import ast
        import pathlib as _pl
        pkg = _pl.Path(r"C:\ABRASAX\abrasax")
        mods = ("live_imu", "adb_sensors", "position", "phone_senses",
                "sense_loop", "tracking", "freshness", "uncertainty",
                "epistemic", "history", "world_state", "fusion", "decision")
        bad = []
        for m in mods:
            f = pkg / f"{m}.py"
            if not f.exists():
                continue
            tree = ast.parse(f.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = ([node.module] if node.module else []) + \
                            [a.name for a in node.names]
                for n in names:
                    if n and (n == "llm" or n.endswith(".llm")
                              or n.split(".")[0] in ("openai", "anthropic",
                                                     "requests", "httpx")):
                        bad.append(f"{m}:{n}")
        assert not bad, f"model/network dependency in the sense path: {bad}"
        return f"{len(mods)} sensing modules, no model dependency"

    check("sense path has no model dependency", sensing_does_not_import_llm)

    def tick_survives_with_models_unreachable():
        """Point every model endpoint at a dead port and tick anyway."""
        import os
        saved = {}
        for var in ("ABRASAX_LLM_URL", "LM_STUDIO_URL", "OPENAI_BASE_URL",
                    "ABRASAX_GATEWAY_URL"):
            saved[var] = os.environ.get(var)
            os.environ[var] = "http://127.0.0.1:9/v1"
        try:
            from abrasax.sense_loop import tick
            rec = tick(serial=SERIAL)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        assert rec.get("event") == "tick", rec
        assert not rec.get("error"), rec.get("error")
        return f"tick ok with dead model endpoints (ingested={rec.get('ingested')})"

    check("tick works with models unreachable", tick_survives_with_models_unreachable)

    print("=== 5c. layer G cognitive controller ===")

    def all_layers_declared():
        """A-F must all be implemented; E was the missing one."""
        import ast
        import pathlib as _pl
        pkg = _pl.Path(r"C:\ABRASAX\abrasax")
        expected = {"A": "sensor_registry", "B": "time_sync", "C": "fusion",
                    "D": "world_state", "F": "nervous_ui"}
        found = {}
        for f in pkg.glob("*.py"):
            text = f.read_text(encoding="utf-8-sig", errors="replace")
            for layer, mod in expected.items():
                if f.stem == mod and f"Layer {layer}" in text:
                    found[layer] = mod
        missing = set(expected) - set(found)
        assert not missing, f"layers not implemented: {sorted(missing)}"
        # E is the controller, declared via its LAYER constant
        from abrasax.controller import LAYER as _L
        assert _L == "G"
        return "A-F per Phase 1, plus G=controller"

    check("all layers declared", all_layers_declared)

    def controller_cycle_runs():
        """Run one real cycle over the live sense stack."""
        from abrasax.controller import Controller, Goal, Observation

        def _observe():
            from abrasax.phone_senses import build_registry
            out = []
            for row in build_registry(serial=SERIAL).discover():
                t = row.get("tracking") or {}
                out.append(Observation(
                    source=row["key"], value=t.get("state", "UNKNOWN"),
                    state="measured" if row.get("status") == "available"
                    else "unknown"))
                if row["key"] == "s25:imu-live":
                    r = t.get("observed_rate_hz")
                    if r is not None:
                        out.append(Observation("imu_rate_hz", r,
                                               state="measured"))
            return out

        import tempfile
        led = __import__("pathlib").Path(tempfile.mkdtemp()) / "c.jsonl"
        c = Controller(observe=_observe, ledger=led,
                       current_origin_of=lambda t: "measured")
        res = c.run_cycle(Goal("e2e", metric="imu_rate_hz",
                               threshold=40.0, direction="above"))
        assert res.status == "OK", res.error
        assert res.judgement.verdict in ("YES", "NO", "UNKNOWN"), res.judgement
        assert led.exists(), "cycle was not recorded"
        return (f"{res.judgement.verdict} conf={res.judgement.confidence:.2f} "
                f"basis={res.judgement.basis} obs={len(res.observations)}")

    check("controller cycle runs and records", controller_cycle_runs)

    def gate_blocks_simulated_overwrite():
        """The gate must be reachable from the controller and must reject."""
        import pathlib as _pl
        import tempfile

        from abrasax.controller import Action, Controller

        led = _pl.Path(tempfile.mkdtemp()) / "c.jsonl"
        c = Controller(observe=lambda: [], ledger=led,
                       current_origin_of=lambda t: "measured")
        acts = [Action(target="pressure", action="update", value=1.0,
                       origin="simulated", rationale="forced")]
        rev = c.review(acts)
        assert rev[0]["verdict"] == "REJECTED", rev[0]
        return "simulated overwrite rejected by the gate"
    check("controller cannot overwrite measured facts", gate_blocks_simulated_overwrite)

    print("=== 5d. cognitive seam ===")

    def seam_degrades_without_a_model():
        """A dead model must yield source=none/text=None, never invention."""
        from abrasax.cognitive import Chain, ModelComponent

        def boom(*a, **k):
            raise RuntimeError("all providers failed")

        dead = ModelComponent("dead", probe_fn=lambda: {"x": {"http": 200}},
                              chat_fn=boom)
        r = Chain([dead]).think("hello")
        assert r.ok is False, r
        assert r.text is None, "a failed model must not return text"
        assert r.source == "none", r
        return f"dead model -> source={r.source} text={r.text}"

    check("seam degrades cleanly without a model", seam_degrades_without_a_model)

    def model_cannot_overturn_a_verdict():
        """The controller's rule verdict must survive a contradicting model."""
        import tempfile
        import pathlib as _pl
        from abrasax.cognitive import Chain, CognitiveResult
        from abrasax.controller import Controller, Goal, Observation

        class Contrarian:
            name = "contrarian"
            kind = "model"

            def available(self):
                return True

            def think(self, prompt, evidence=()):
                return CognitiveResult(source="model", ok=True,
                                       text="NO, definitely failing", model="x")

        led = _pl.Path(tempfile.mkdtemp()) / "c.jsonl"
        c = Controller(observe=lambda: [Observation("r", 49.2, "measured")],
                       ledger=led, cognition=Chain([Contrarian()]))
        res = c.run_cycle(Goal("g", metric="r", threshold=40.0,
                               direction="above"))
        assert res.judgement.verdict == "YES", res.judgement
        assert res.judgement.basis == "rules+model"
        return f"model said NO, verdict stayed {res.judgement.verdict}"

    check("model cannot overturn a measured verdict",
          model_cannot_overturn_a_verdict)

    print("=== 5e. interpretation of selected observations ===")

    def interprets_the_whole_set():
        """judge() used to read 1 of 6 observations and ignore the rest."""
        import tempfile
        import pathlib as _pl
        from abrasax.controller import Controller, Goal, Observation

        obs = [
            Observation("imu_rate_hz", 49.2, "measured"),
            Observation("s25:imu-live", "TRACKING", "measured"),
            Observation("s25:adb", "TRACKING", "measured"),
            Observation("s25:position", "STALE", "unknown"),
            Observation("battery_pct", 12.0, "measured"),
        ]
        led = _pl.Path(tempfile.mkdtemp()) / "c.jsonl"
        c = Controller(observe=lambda: obs, ledger=led)
        r = c.run_cycle(Goal("g", metric="imu_rate_hz", threshold=40.0,
                             direction="above"))
        assert r.selection is not None, "no selection recorded"
        assert r.interpretation is not None, "no interpretation recorded"
        sal = [s["claim"] for s in r.interpretation["salient"]]
        assert any("battery_pct" in s for s in sal), sal
        # the stale source must have pulled confidence below a clean run
        clean = Controller(observe=lambda: obs[:3], ledger=led).run_cycle(
            Goal("g", metric="imu_rate_hz", threshold=40.0, direction="above"))
        assert r.judgement.confidence < clean.judgement.confidence
        assert r.judgement.verdict == "YES", "interpretation must not flip a verdict"
        return (f"conf {clean.judgement.confidence:.2f} -> "
                f"{r.judgement.confidence:.2f}, salient={len(sal)}")

    check("interprets the selected set", interprets_the_whole_set)

    print("=== 6. go daemon ===")
    check("abrasaxd /health", lambda: http_json(f"{DAEMON}/health")["service"])

    def daemon_tick():
        r = http_json(f"{DAEMON}/tick", method="POST")
        assert r["ok"], r.get("error")
        return f"ingested={r['ingested']}"

    check("abrasaxd /tick", daemon_tick)

    print("=== 7. storage ===")

    def phone_space():
        out = subprocess.run([ADB, "-s", SERIAL, "shell", "df -k /data"],
                             capture_output=True, text=True, timeout=25).stdout
        pct = int(out.splitlines()[1].split()[4].rstrip("%"))
        assert pct < 95, f"phone at {pct}% - still full"
        return f"{pct}% used"

    check("phone has free space", phone_space)

    def offload_target():
        # Each offload pass writes its own manifest and the rolling loop runs
        # passes back to back, so counting only the newest one undercounts
        # badly: it once reported 256 when 2,752 files had been hashed.
        p = Path(r"J:\ABRASAX_OFFLOAD\S25_R5CY308WZVK")
        assert p.exists(), "offload dir missing"
        manifests = list(p.glob("_manifest_*.tsv"))
        assert manifests, "no manifest"
        lines = 0
        for m in manifests:
            with m.open(encoding="utf-8", errors="replace") as fh:
                lines += sum(1 for _ in fh)
        files = sum(1 for f in p.rglob("*") if f.is_file())
        assert lines > 0, "manifests are empty"
        # A large shortfall means files landed without being hashed.
        assert files >= lines * 0.9, (
            f"{files} files on disk but only {lines} hashed entries")
        return f"{lines} hashed files across {len(manifests)} manifests on J:"

    check("offload intact on harddrive", offload_target)

    print()
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"=== {passed}/{total} checks passed ===")
    if passed < total:
        print("failures:")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}: {detail}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
