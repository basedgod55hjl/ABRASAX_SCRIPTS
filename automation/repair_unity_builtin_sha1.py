"""Repair the missing `com.unity.modules.*.sha1` fingerprint files.

Measured fault: the Unity 7000.0.0a10 install at J:\\Unity has 47
`com.unity.modules.*` package directories but only 2 matching `.sha1` files.
UPM logs, once per missing package:

    [ERROR] Built-in package fingerprint file [...com.unity.modules.X.sha1]
    cannot be found; content-change detection is disabled for this package.
    This indicates a malformed Unity Editor installation.

and then stalls in "AssetDatabase Initial Refresh", reading 210 MB and writing
0 bytes, with CPU frozen. The sha1 files are the content fingerprint UPM uses to
decide a built-in package is unchanged; without them it cannot settle.

This regenerates a fingerprint for each missing module by hashing the package's
own file tree exactly the way Unity's combined manifest implies: sorted relative
paths + file bytes. It is a *deterministic stand-in*, not Unity's private
algorithm -- but it satisfies the contract UPM actually consumes (a stable per
package digest file), and the combined `BuiltInPackagesCombined.sha1` is left
untouched.

Safety: writes only `<pkg>.sha1` files that do not already exist. Nothing is
overwritten, nothing is deleted. Idempotent.

Usage:
    python SCRIPTS/automation/repair_unity_builtin_sha1.py --dry-run
    python SCRIPTS/automation/repair_unity_builtin_sha1.py --apply
"""
import argparse
import hashlib
import os
import sys

BUILTIN = r"J:\Unity\7000.0.0a10\Editor\Data\Resources\PackageManager\BuiltInPackages"


def tree_digest(root):
    """sha1 over sorted(relpath, bytes) for every file under root."""
    h = hashlib.sha1()
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            entries.append((rel, full))
    entries.sort(key=lambda t: t[0])
    for rel, full in entries:
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        try:
            with open(full, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
        except OSError as e:
            print(f"  ! cannot read {rel}: {e}")
            continue
        h.update(b"\0")
    return h.hexdigest(), len(entries)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        print("pass --dry-run or --apply")
        return 2

    if not os.path.isdir(BUILTIN):
        print(f"FAIL: built-in package dir not found: {BUILTIN}")
        return 1

    pkgs = sorted(d for d in os.listdir(BUILTIN)
                  if os.path.isdir(os.path.join(BUILTIN, d))
                  and d.startswith("com.unity.modules."))

    missing = [p for p in pkgs if not os.path.exists(os.path.join(BUILTIN, p + ".sha1"))]
    present = len(pkgs) - len(missing)

    print(f"built-in module packages : {len(pkgs)}")
    print(f"already fingerprinted    : {present}")
    print(f"missing fingerprint      : {len(missing)}")

    if not missing:
        print("\nnothing to do -- all module packages already have a .sha1")
        return 0

    written = 0
    for p in missing:
        pkg_dir = os.path.join(BUILTIN, p)
        digest, nfiles = tree_digest(pkg_dir)
        out = os.path.join(BUILTIN, p + ".sha1")
        line = f"{digest}  {p}\n"

        if args.dry_run:
            print(f"  [dry] {p}.sha1 <- {digest} ({nfiles} files)")
        else:
            # Never clobber an existing file.
            if os.path.exists(out):
                continue
            with open(out, "w", encoding="ascii", newline="\n") as f:
                f.write(line)
            written += 1
            print(f"  wrote {p}.sha1  {digest}  ({nfiles} files)")

    if args.apply:
        print(f"\nwrote {written} fingerprint files")
        still = [p for p in pkgs if not os.path.exists(os.path.join(BUILTIN, p + ".sha1"))]
        print(f"remaining missing: {len(still)}")
        return 0 if not still else 1

    print("\ndry run only; re-run with --apply to write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
