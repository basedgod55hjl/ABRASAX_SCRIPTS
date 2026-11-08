"""Guard for the crash hardening applied on 2026-11-02.

`DOC/FINDINGS_PC_CRASH-20261102.md` records three kernel dumps that name two
minifilters (`cldflt!HsmFltPreSetRenameInformation`, `fileinfo!FIStreamQueryInfo`)
and the settings that keep them out of the I/O path. Those settings are registry
values and power-profile indices, so nothing stops a driver update, an OneDrive
update or a `powercfg` call from putting them back. This script reads the machine
and says whether the state the dumps were fixed for still holds.

    python SCRIPTS\\automation\\pc_crash_guard.py            # table, exit 1 on drift
    python SCRIPTS\\automation\\pc_crash_guard.py --json     # machine readable

`evaluate()` is pure: it takes a dict of raw readings and returns verdicts, so the
policy can be tested without touching the registry. `paging_values()` is pure too,
because the registry returns `PagingFiles` in at least three different shapes
(`['C:\\pagefile.sys 24576 24576']`, a bare string, or a REG_MULTI_SZ list) and the
first version of this script crashed on the first one.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

EXPECTED = {
    "CldFlt.Start": 4,
    "FileInfo.Start": 4,
    "GraphicsDrivers.TdrDelay": 10,
    "GraphicsDrivers.TdrDdiDelay": 10,
    "SessionManagerPower.HiberbootEnabled": 0,
    "PageFile.InitialSize": 24576,
    "PageFile.MaximumSize": 24576,
    "CldFlt.Instances": 0,
    "Power.UsbSelectiveSuspendAC": 0,
    "Power.UsbSelectiveSuspendDC": 0,
    "Power.DiskIdleTimeoutAC": 0,
    "Power.DiskIdleTimeoutDC": 0,
}

USB_SUB = "2a737441-1930-4402-8d77-b2bebba308a3"
USB_SUSPEND = "48e6b7a6-50f5-4782-a5d4-53bb8f07e226"
DISK_SUB = "0012ee47-9041-4b5d-9b77-535fba8b1442"
DISK_IDLE = "6738e2c4-e8a5-4a42-b16a-e040e769756e"


def evaluate(state):
    """Return one verdict per expected key: [(key, ok, expected, actual)]."""
    out = []
    for key, want in EXPECTED.items():
        got = state.get(key)
        out.append((key, got == want, want, got))
    return out


def paging_values(raw):
    """Pull (initial, maximum) out of whatever shape PagingFiles came back in."""
    if raw is None:
        return None, None
    if isinstance(raw, (list, tuple)):
        text = " ".join(str(part) for part in raw)
    else:
        text = str(raw)
    text = text.replace("[", " ").replace("]", " ").replace("'", " ").replace('"', " ")
    numbers = re.findall(r"\b(\d{3,6})\b", text)
    if len(numbers) < 2:
        return None, None
    return int(numbers[0]), int(numbers[1])


def _reg(path, name):
    try:
        import winreg
    except ImportError:  # pragma: no cover - windows only
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return int(value)
    except (OSError, ValueError):
        return None


def _run(cmd):
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return done.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _filter_instances(name):
    """Count instances of a minifilter via `fltmc filters`; None if unavailable."""
    text = _run(["fltmc", "filters"])
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].lower() == name.lower():
            try:
                return int(parts[1])
            except ValueError:
                return None
    return None


def _power_index(sub, setting):
    """Read the current AC/DC index of one power setting (hex in the output)."""
    out = _run(["powercfg", "/query", "SCHEME_CURRENT", sub, setting])
    ac = dc = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Current AC Power Setting Index:"):
            ac = int(line.rsplit(":", 1)[1].strip(), 16)
        elif line.startswith("Current DC Power Setting Index:"):
            dc = int(line.rsplit(":", 1)[1].strip(), 16)
    return ac, dc


def read_state():
    """Read the live machine. Every key is present; unreadable values are None."""
    import winreg

    state = {}
    state["CldFlt.Start"] = _reg(r"SYSTEM\CurrentControlSet\Services\CldFlt", "Start")
    state["FileInfo.Start"] = _reg(r"SYSTEM\CurrentControlSet\Services\FileInfo", "Start")
    state["GraphicsDrivers.TdrDelay"] = _reg(
        r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "TdrDelay")
    state["GraphicsDrivers.TdrDdiDelay"] = _reg(
        r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "TdrDdiDelay")
    state["SessionManagerPower.HiberbootEnabled"] = _reg(
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Power", "HiberbootEnabled")
    state["CldFlt.Instances"] = _filter_instances("CldFlt")

    raw_paging = None
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
        ) as key:
            raw_paging = winreg.QueryValueEx(key, "PagingFiles")[0]
    except OSError:
        pass
    state["PageFile.InitialSize"], state["PageFile.MaximumSize"] = paging_values(raw_paging)

    usb_ac, usb_dc = _power_index(USB_SUB, USB_SUSPEND)
    state["Power.UsbSelectiveSuspendAC"] = usb_ac
    state["Power.UsbSelectiveSuspendDC"] = usb_dc
    disk_ac, disk_dc = _power_index(DISK_SUB, DISK_IDLE)
    state["Power.DiskIdleTimeoutAC"] = disk_ac
    state["Power.DiskIdleTimeoutDC"] = disk_dc
    return state


def main(argv=None):
    ap = argparse.ArgumentParser(description="verify the 2026-11-02 crash hardening")
    ap.add_argument("--json", action="store_true", help="print the raw state as json")
    args = ap.parse_args(argv)

    try:
        state = read_state()
    except Exception as exc:  # noqa: BLE001 - a guard that crashes is not a guard
        print("pc_crash_guard: cannot read this machine: %s" % exc)
        return 2

    if args.json:
        print(json.dumps(state, indent=2, sort_keys=True))
        return 0

    verdicts = evaluate(state)
    failed = 0
    for key, ok, want, got in verdicts:
        failed += 0 if ok else 1
        print("%-38s %-5s want=%-8s got=%s" % (key, "ok" if ok else "DRIFT", want, got))
    print("")
    print("%d/%d checks pass" % (len(verdicts) - failed, len(verdicts)))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
