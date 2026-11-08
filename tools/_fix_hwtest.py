import pathlib

# Two tests hardcode serial="R5CY308WZVK" and assert a tick succeeds. When the
# phone is unplugged they FAIL rather than SKIP - reporting a hardware absence
# as a code defect. The suite already uses ABRASAX_LIVE_ADB gating for exactly
# this reason elsewhere; these two were written while the device happened to be
# attached.
#
# A test that cannot run without hardware should say so, not blame the code.

p = pathlib.Path(r"C:\ABRASAX\TESTS\python\test_isolation.py")
src = p.read_text(encoding="utf-8")

old = '''@pytest.mark.slow
def test_pipeline_completes_while_the_renderer_raises():
    """The guarantee, tested end to end with the real pipeline."""
    from abrasax.sense_loop import tick
    from abrasax.world_state import default

    ws = default()
    before = ws.snapshot().get("events_total")'''

new = '''def _device_attached() -> bool:
    """True when adb reports an authorised device. Hardware is optional here."""
    import subprocess
    try:
        from abrasax.adb_sensors import find_adb
        out = subprocess.run([find_adb(), "devices"], capture_output=True,
                             text=True, timeout=15).stdout
    except Exception:  # noqa: BLE001 - absence is a skip, not a failure
        return False
    return any(line.split()[1] == "device"
               for line in out.splitlines()[1:] if len(line.split()) >= 2)


@pytest.mark.slow
@pytest.mark.skipif(not _device_attached(),
                    reason="no adb device attached; this test drives real hardware")
def test_pipeline_completes_while_the_renderer_raises():
    """The guarantee, tested end to end with the real pipeline."""
    from abrasax.sense_loop import tick
    from abrasax.world_state import default

    ws = default()
    before = ws.snapshot().get("events_total")'''
assert old in src, "isolation test not found"
src = src.replace(old, new, 1)

# the assertion should blame the code, not a missing phone
src = src.replace(
    '''        rec = tick(serial="R5CY308WZVK")
        assert not rec.get("error"), rec.get("error")
        assert rec.get("ingested", 0) >= 1''',
    '''        rec = tick()
        assert not rec.get("error"), rec.get("error")
        assert rec.get("ingested", 0) >= 1''',
    1,
)
p.write_text(src, encoding="utf-8", newline="\n")
print("patched isolation test: hardware absence is a skip")

# the nervous_ui HTTP test asserted an exact title that changed with the
# masthead work; make it assert the contract (a page is served) not the wording
q = pathlib.Path(r"C:\ABRASAX\TESTS\python\test_nervous_ui.py")
qs = q.read_text(encoding="utf-8")
for i, line in enumerate(qs.splitlines(), 1):
    if "ABRAXIS WORLD MODEL" in line or "ABRASAX WORLD MODEL" in line:
        print(f"  nervous_ui test line {i}: {line.strip()[:80]}")
