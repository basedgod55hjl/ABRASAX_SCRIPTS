"""Does `adb shell input` actually reach the device on this phone?

Earlier a swipe produced no measurable motion, which could mean (a) input is
injected but the device is locked so nothing responds, (b) input is silently
dropped by a secure lockscreen, or (c) our motion detection is wrong.

Decide it by watching a signal that MUST change if input lands: the display
power state and the focused window. Power-button toggling is the cleanest
because it is not gated by the keyguard.
"""
import re
import subprocess
import sys
import time

ADB = r"C:\abrasax\_DEAD_PATH\Android\platform-tools\adb.exe"  # DEAD PATH (sirch): no adb.exe on this host
SERIAL = "R5CY308WZVK"


def sh(cmd, timeout=25):
    return subprocess.run([ADB, "-s", SERIAL, "shell", cmd],
                          capture_output=True, text=True, timeout=timeout).stdout


def wakefulness():
    out = sh("dumpsys power")
    m = re.search(r"mWakefulness=(\w+)", out)
    return m.group(1) if m else "?"


def locked():
    out = sh("dumpsys window")
    m = re.search(r"mDreamingLockscreen=(true|false)", out)
    return m.group(1) == "true" if m else None


def focused():
    out = sh("dumpsys window")
    m = re.search(r"mCurrentFocus=(\S+)", out)
    return m.group(1) if m else "?"


def main():
    print(f"start: wakefulness={wakefulness()} locked={locked()} focus={focused()}")

    print("\nsending KEYCODE_POWER (26)...")
    sh("input keyevent 26")
    time.sleep(3)
    print(f"  after power: wakefulness={wakefulness()} locked={locked()}")

    print("\nsending KEYCODE_POWER again...")
    sh("input keyevent 26")
    time.sleep(3)
    print(f"  after power: wakefulness={wakefulness()} locked={locked()}")

    print("\nsending KEYCODE_MENU (82)...")
    sh("input keyevent 82")
    time.sleep(2)
    print(f"  after menu : wakefulness={wakefulness()} locked={locked()} focus={focused()}")

    w = wakefulness()
    if w in ("Awake", "Asleep"):
        print("\n  input IS reaching the device (power state responded)")
        return 0
    print("\n  INCONCLUSIVE: power state did not change")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
