import pathlib

p = pathlib.Path(r"C:\ABRASAX\abrasax\sensor_registry.py")
src = p.read_text(encoding="utf-8")

# discover() called each provider's tracking() and status() unguarded. When the
# phone was unplugged, LiveImu.ensure_forward() raised LiveImuError("no device
# attached") and the exception escaped discover() - taking down the whole
# registry listing, and with it build_state() and the entire dashboard.
#
# One provider being unreachable is the NORMAL case for an optional sense. It
# must degrade that provider's row, not the catalogue.
old = '''    def discover(self) -> list[dict]:
        """Return one status record per registered provider, measured now."""
        out: list[dict] = []
        for key, p in self._providers.items():
            # Providers in this tree are duck-typed, not all subclasses of
            # SensorProvider, so ask for tracking defensively rather than
            # assuming the base class supplies it.
            trk = getattr(p, "tracking", None)
            tracking = trk() if callable(trk) else {
                "state": "UNKNOWN", "healthy": False,
                "reason": f"{type(p).__name__} does not report tracking"}
            out.append({"key": key, "status": p.status(),
                        "tracking": tracking, **p.capabilities()})
        return sorted(out, key=lambda r: r["key"])'''

new = '''    def discover(self) -> list[dict]:
        """Return one status record per registered provider, measured now.

        Every probe is guarded. A provider that raises is reported as
        disconnected with the reason - it must not take the catalogue with it.
        An unplugged phone is the normal case for an optional sense, and a
        registry that cannot list its other providers because of it is worse
        than useless: it blanks the dashboard.
        """
        out: list[dict] = []
        for key, p in self._providers.items():
            row: dict = {"key": key}

            try:
                row["status"] = p.status()
            except Exception as exc:  # noqa: BLE001 - one provider, not the list
                row["status"] = "disconnected"
                row["status_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"

            trk = getattr(p, "tracking", None)
            if callable(trk):
                try:
                    row["tracking"] = trk()
                except Exception as exc:  # noqa: BLE001
                    row["tracking"] = {
                        "state": "LOST", "healthy": False,
                        "reason": f"tracking probe raised: "
                                  f"{type(exc).__name__}: {str(exc)[:140]}"}
            else:
                row["tracking"] = {
                    "state": "UNKNOWN", "healthy": False,
                    "reason": f"{type(p).__name__} does not report tracking"}

            try:
                row.update(p.capabilities())
            except Exception as exc:  # noqa: BLE001
                row.setdefault("provider_id", getattr(p, "provider_id", "?"))
                row["capabilities_error"] = type(exc).__name__

            out.append(row)
        return sorted(out, key=lambda r: r["key"])'''
assert old in src, "discover not found"
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8", newline="\n")
print("patched discover(): one provider cannot break the catalogue")
