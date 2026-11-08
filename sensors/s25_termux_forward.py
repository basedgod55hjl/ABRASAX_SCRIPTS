#!/usr/bin/env python3
"""Forward Galaxy S25 Ultra sensors from Termux to the ABRASAX gateway.

Why this exists next to the browser client: Chrome on Android treats a plain
``http://<lan-ip>/`` page as an insecure context and can refuse DeviceMotion,
DeviceOrientation and the Generic Sensor API.  Termux has no such restriction:
it reads the same SensorManager through the ``termux-sensor`` CLI and posts
straight to the gateway.

Wire contract (owned by the gateway agent -- do not change unilaterally):

    POST /v1/sensors/ingest  {"mag":[3],"imu":[6],"env":[2], ...}
    POST /v1/sensors/batch   {"samples":[<ingest body>, ...]}  (max 256)
    GET  /v1/sensors/state
    Authorization: Bearer <ABRASAX_GATEWAY_TOKEN>   (when configured)

Field order is fixed and shared with the web client (UI/abrasax-ui/web/sensors):

    mag = [mx, my, mz]                       microtesla
    imu = [ax, ay, az, gx, gy, gz]           m/s^2 (gravity included), rad/s
    env = [temperature_c, pressure_hpa]      degrees C, hectopascal

Android's SensorManager already reports exactly those units, so nothing is
rescaled here.  A missing sensor contributes zeros; the payload shape stays
fixed regardless of which sensors the phone exposes.

Security rules baked in:
  * the token is read from an environment variable only -- never argv (shell
    history), never a file this script writes, never a log line;
  * only the token's presence is logged, never its value;
  * a request body is never echoed back into a log on failure.

Usage:
    termux-sensor -l                               # see what the phone has
    python s25_termux_forward.py --once --dry-run  # one payload, no network
    python s25_termux_forward.py --dry-run --hz 2  # stream payloads locally
    export ABRASAX_GATEWAY_TOKEN=...
    python s25_termux_forward.py --base-url http://192.168.1.20:9001

Exit codes: 0 ok, 2 configuration/validation, 3 termux-sensor missing,
4 sensor read/parse failure.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable, Iterable, Sequence

VERSION = "1.0.0"

DEFAULT_BASE_URL = "http://127.0.0.1:9001"
DEFAULT_TOKEN_ENV = "ABRASAX_GATEWAY_TOKEN"
DEFAULT_HZ = 10.0
DEFAULT_BATCH = 20
DEFAULT_SENSORS = "accelerometer,gyroscope,magnetometer,pressure"
DEFAULT_RF_FINGERPRINT = "termux-s25"
DEFAULT_RETRIES = 5
DEFAULT_TIMEOUT = 10.0
MAX_BATCH = 256
TERMUX_ENV = "ABRASAX_TERMUX_SENSOR"

INGEST_PATH = "/v1/sensors/ingest"
BATCH_PATH = "/v1/sensors/batch"
STATE_PATH = "/v1/sensors/state"

# canonical name -> lowercase substrings that identify it
SENSOR_ALIASES: dict[str, tuple[str, ...]] = {
    "accel": ("accelerometer",),
    "gyro": ("gyroscope",),
    "mag": ("magnetometer", "magnetic field", "magnetic"),
    "pressure": ("pressure", "barometer"),
    "temperature": ("temperature",),
    "light": ("light", "lux"),
}

# A reading from an uncalibrated or gravity-removed variant is still usable,
# but a calibrated / gravity-included sibling is preferable when both exist.
SENSOR_PENALTIES = ("uncalibrated", "linear acceleration", "game rotation")


class LineProtocolError(RuntimeError):
    """termux-sensor produced something we cannot interpret."""


class PostError(RuntimeError):
    """A POST failed. ``status`` is 0 for transport failures."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def log(message: str) -> None:
    """Progress goes to stderr so stdout stays machine-readable in --dry-run."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def iso_now() -> str:
    return (datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"))


def _as_float(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{what} must be a number, got {type(value).__name__}")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{what} must be finite, got {out!r}")
    return out


def _vector(values: object, length: int) -> list[float]:
    """Coerce a sensor reading to ``length`` floats, zero-padding short reads.

    Missing (None) and empty reads become zeros so the payload shape does not
    change with sensor availability.  Extra values are dropped: a few Android
    builds append a timestamp or accuracy channel.
    """
    if values is None:
        return [0.0] * length
    if isinstance(values, (int, float)) and not isinstance(values, bool):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return [0.0] * length
    out = [_as_float(v, "sensor value") for v in list(values)[:length]]
    return out + [0.0] * (length - len(out))


def _extract_values(node: object) -> list[float] | None:
    """Find the numeric vector inside one termux-sensor entry.

    Known shapes, all seen in the wild:
      {"values": [1, 2, 3]}
      {"values": [[1, 2, 3]]}          # batched single sample
      {"values": [[...], [...]]}       # -n > 1; the newest sample is last
      [1, 2, 3]
    """
    if isinstance(node, dict):
        node = node.get("values")
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        return [float(node)]
    if not isinstance(node, (list, tuple)) or not node:
        return None
    if isinstance(node[0], (list, tuple)):
        node = node[-1]
    if not isinstance(node, (list, tuple)):
        return None
    out: list[float] = []
    for item in node:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        out.append(float(item))
    return out


def classify_sensor(name: str) -> str | None:
    low = name.lower()
    for canonical, aliases in SENSOR_ALIASES.items():
        if any(alias in low for alias in aliases):
            return canonical
    return None


def _penalty(name: str) -> int:
    low = name.lower()
    return sum(1 for token in SENSOR_PENALTIES if token in low)


def parse_termux_sensor_output(text: str) -> dict[str, list[float]]:
    """Map ``termux-sensor -n 1`` JSON to canonical names.

    Returns only sensors we recognise; unknown entries are ignored rather than
    failing the sample (Samsung ROMs add vendor channels that come and go).
    """
    if not text or not text.strip():
        raise LineProtocolError("termux-sensor produced no output")
    raw = text.strip()
    try:
        payload = json.loads(raw)
    except ValueError:
        # A shell banner or a partially flushed stream can precede the object.
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise LineProtocolError(
                f"termux-sensor output is not JSON: {raw[:160]!r}") from None
        try:
            payload = json.loads(raw[start:end + 1])
        except ValueError:
            raise LineProtocolError(
                f"termux-sensor output is not JSON: {raw[:160]!r}") from None

    # Some builds emit a one-element array around the object.
    if isinstance(payload, list):
        if not payload:
            raise LineProtocolError("termux-sensor returned an empty array")
        payload = payload[-1]
    if not isinstance(payload, dict):
        raise LineProtocolError(
            f"termux-sensor returned {type(payload).__name__}, expected an object")

    best: dict[str, tuple[int, list[float]]] = {}
    for name, node in payload.items():
        canonical = classify_sensor(str(name))
        if canonical is None:
            continue
        values = _extract_values(node)
        if values is None:
            continue
        rank = _penalty(str(name))
        if canonical not in best or rank < best[canonical][0]:
            best[canonical] = (rank, values)
    if not best:
        raise LineProtocolError(
            "no accelerometer/gyroscope/magnetometer/pressure entry in "
            f"{sorted(payload)[:8]}")
    return {name: values for name, (_rank, values) in best.items()}


def build_sample(readings: dict[str, Sequence[float]],
                 *,
                 timestamp: str | None = None,
                 rf_fingerprint: str = DEFAULT_RF_FINGERPRINT,
                 learn: bool = False) -> dict:
    """Build the exact ingest body from canonical sensor readings."""
    mag = _vector(readings.get("mag"), 3)
    imu = _vector(readings.get("accel"), 3) + _vector(readings.get("gyro"), 3)
    env = _vector(readings.get("temperature"), 1) + _vector(readings.get("pressure"), 1)

    sample: dict = {
        "mag": [round(v, 6) for v in mag],
        "imu": [round(v, 6) for v in imu],
        "env": [round(v, 6) for v in env],
    }
    if rf_fingerprint:
        sample["rf_fingerprint"] = str(rf_fingerprint)[:128]
    sample["timestamp"] = timestamp or iso_now()
    sample["learn"] = bool(learn)
    return sample


def _parse_timestamp(value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"timestamp is not ISO-8601: {value!r}") from None


def validate_sample(sample: object) -> dict:
    """Strict shape check for one ingest body. Raises ValueError."""
    if not isinstance(sample, dict):
        raise ValueError("sample must be an object")
    for key, length in (("mag", 3), ("imu", 6), ("env", 2)):
        if key not in sample:
            raise ValueError(f"missing {key!r}")
        values = sample[key]
        if not isinstance(values, (list, tuple)) or len(values) != length:
            raise ValueError(f"{key!r} must be an array of {length} numbers")
        for i, value in enumerate(values):
            _as_float(value, f"{key}[{i}]")
    if "rf_fingerprint" in sample:
        rf = sample["rf_fingerprint"]
        if not isinstance(rf, str) or not rf:
            raise ValueError("rf_fingerprint must be a non-empty string when present")
    if "timestamp" in sample:
        _parse_timestamp(sample["timestamp"])
    if "learn" in sample and not isinstance(sample["learn"], bool):
        raise ValueError("learn must be a boolean")
    return sample


def validate_batch(samples: object) -> list:
    if not isinstance(samples, list) or not samples:
        raise ValueError("samples must be a non-empty array")
    if len(samples) > MAX_BATCH:
        raise ValueError(f"batch has {len(samples)} samples; limit is {MAX_BATCH}")
    for i, sample in enumerate(samples):
        try:
            validate_sample(sample)
        except ValueError as exc:
            raise ValueError(f"samples[{i}]: {exc}") from None
    return samples


# ---------------------------------------------------------------------------
# transport
# ---------------------------------------------------------------------------

def _decode_body(raw: bytes) -> dict:
    if not raw:
        return {}
    text = raw.decode("utf-8", "replace")
    try:
        parsed = json.loads(text)
    except ValueError:
        return {"raw": text[:500]}
    return parsed if isinstance(parsed, dict) else {"response": parsed}


def _post_json(base_url: str, path: str, payload: dict, token: str,
               timeout: float = DEFAULT_TIMEOUT) -> tuple[int, dict]:
    url = base_url.rstrip("/") + path
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"abrasax-s25-forwarder/{VERSION}",
    }
    if token:
        # Never logged, never placed in the URL.
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, _decode_body(response.read(65536))
    except urllib.error.HTTPError as exc:
        detail = _decode_body(exc.read(4096) if exc.fp else b"")
        message = detail.get("error") if isinstance(detail.get("error"), str) else None
        if message is None and isinstance(detail.get("error"), dict):
            message = detail["error"].get("message")
        if message is None:
            message = detail.get("raw") or f"HTTP {exc.code}"
        raise PostError(int(exc.code), str(message)[:400]) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise PostError(0, f"connection failed: {reason}") from None


def endpoint_for(count: int) -> str:
    return INGEST_PATH if count == 1 else BATCH_PATH


def body_for(samples: Sequence[dict]) -> dict:
    return samples[0] if len(samples) == 1 else {"samples": list(samples)}


def publish(base_url: str, samples: Sequence[dict], token: str, *,
            timeout: float = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES,
            sleep: Callable[[float], None] = time.sleep) -> tuple[int, dict]:
    """POST one sample (ingest) or many (batch), retrying transient failures."""
    validate_batch(list(samples))
    count = len(samples)
    path = endpoint_for(count)
    last: PostError | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            return _post_json(base_url, path, body_for(samples), token, timeout)
        except PostError as exc:
            last = exc
            # 400/413/422 will not become valid on retry; everything else might.
            retryable = not (400 <= exc.status < 500 and exc.status not in (401, 403, 429))
            if not retryable or attempt >= max(1, retries):
                raise
            delay = min(15.0, 0.5 * (2 ** (attempt - 1))) * random.uniform(0.8, 1.2)
            if exc.status in (401, 403):
                log(f"{exc.status} auth rejected; check the token env var "
                    f"(retry {attempt}/{retries} in {delay:.1f}s)")
            else:
                log(f"POST {path} failed ({exc.status}: {exc}); "
                    f"retry {attempt}/{retries} in {delay:.1f}s")
            sleep(delay)
    assert last is not None  # unreachable: the loop either returns or raises
    raise last


# ---------------------------------------------------------------------------
# termux-sensor
# ---------------------------------------------------------------------------

def termux_sensor_exe() -> str | None:
    override = (os.environ.get(TERMUX_ENV) or "").strip()
    if override:
        return override if os.path.isfile(override) else None
    return shutil.which("termux-sensor")


def termux_available() -> bool:
    return termux_sensor_exe() is not None


MISSING_TERMUX_HELP = """\
termux-sensor not found.

Install on the phone from F-Droid (the Play Store build is discontinued):
  pkg update && pkg install termux-api
Then install the matching "Termux:API" app from the same F-Droid source,
open Termux once, and grant the sensor permission when Android asks.
Check the bridge:
  termux-sensor -l
If the binary lives elsewhere:
  export ABRASAX_TERMUX_SENSOR=/data/data/com.termux/files/usr/bin/termux-sensor
"""


def read_sensors(sensors: str, sample_ms: int,
                 timeout: float | None = None) -> str:
    """Run one bounded ``termux-sensor -n 1`` call and return its stdout."""
    exe = termux_sensor_exe()
    if exe is None:
        raise FileNotFoundError("termux-sensor")
    if timeout is None:
        timeout = max(3.0, (sample_ms / 1000.0) * 4.0 + 2.0)
    command = [exe, "-s", sensors, "-n", "1", "-d", str(int(sample_ms))]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout)
    except subprocess.TimeoutExpired:
        raise LineProtocolError(
            f"termux-sensor did not answer within {timeout:.1f}s") from None
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else f"exit {result.returncode}"
        raise LineProtocolError(f"termux-sensor failed: {tail[:200]}")
    return result.stdout


def read_sample(sensors: str, sample_ms: int, *,
                rf_fingerprint: str, learn: bool) -> tuple[dict, dict]:
    """Read once, parse, and build a validated sample.

    Returns (sample, readings) so the caller can report which sensors were
    actually present without adding non-contract keys to the payload.
    """
    readings = parse_termux_sensor_output(read_sensors(sensors, sample_ms))
    sample = build_sample(readings, rf_fingerprint=rf_fingerprint, learn=learn)
    validate_sample(sample)
    return sample, readings


def missing_channels(readings: dict) -> list[str]:
    needed = ("accel", "gyro", "mag", "pressure", "temperature")
    return [name for name in needed if not readings.get(name)]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="s25_termux_forward.py",
        description="Forward Galaxy S25 Ultra sensors from Termux to ABRASAX.",
        epilog="The token is read from an environment variable, never argv.",
    )
    parser.add_argument("--base-url",
                        default=os.environ.get("ABRASAX_GATEWAY_URL", DEFAULT_BASE_URL),
                        help=f"gateway origin (default {DEFAULT_BASE_URL})")
    parser.add_argument("--token-env", default=DEFAULT_TOKEN_ENV,
                        help=f"env var holding the bearer token (default {DEFAULT_TOKEN_ENV})")
    parser.add_argument("--hz", type=float, default=DEFAULT_HZ,
                        help=f"samples per second (default {DEFAULT_HZ:g})")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH,
                        help=f"samples per POST, 1-{MAX_BATCH} (default {DEFAULT_BATCH})")
    parser.add_argument("--sensors", default=DEFAULT_SENSORS,
                        help=f"comma-separated termux-sensor names (default {DEFAULT_SENSORS})")
    parser.add_argument("--sample-ms", type=int, default=0,
                        help="termux-sensor -d delay in ms (default: 1000/hz)")
    parser.add_argument("--once", action="store_true",
                        help="send one sample and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="print payloads to stdout, never touch the network")
    parser.add_argument("--learn", action="store_true",
                        help="set learn=true on every sample")
    parser.add_argument("--rf-fingerprint", default=DEFAULT_RF_FINGERPRINT,
                        help=f"rf_fingerprint field (default {DEFAULT_RF_FINGERPRINT})")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES,
                        help=f"POST attempts per batch (default {DEFAULT_RETRIES})")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help=f"HTTP timeout seconds (default {DEFAULT_TIMEOUT:g})")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if not (0.1 <= args.hz <= 200.0):
        raise SystemExit(f"--hz must be between 0.1 and 200, got {args.hz}")
    if not (1 <= args.batch <= MAX_BATCH):
        raise SystemExit(f"--batch must be between 1 and {MAX_BATCH}, got {args.batch}")
    if not (0 <= args.sample_ms <= 60000):
        raise SystemExit(f"--sample-ms must be between 0 and 60000, got {args.sample_ms}")
    if args.retries < 1:
        raise SystemExit(f"--retries must be >= 1, got {args.retries}")
    if not args.base_url.startswith(("http://", "https://")):
        raise SystemExit("--base-url must start with http:// or https://")
    if not args.sensors.strip():
        raise SystemExit("--sensors must not be empty")


def _run(args: argparse.Namespace) -> int:
    _validate_args(args)
    sample_ms = args.sample_ms or max(1, int(round(1000.0 / args.hz)))
    token = (os.environ.get(args.token_env) or "").strip()
    base_url = args.base_url.rstrip("/")

    if not args.dry_run:
        log(f"gateway {base_url}  token={'present' if token else 'absent'}  "
            f"hz={args.hz:g}  batch={args.batch}  sensors={args.sensors}")
        if not token:
            log(f"{args.token_env} is unset; posting unauthenticated "
                "(an open gateway accepts it, a token gateway answers 401)")
    if not termux_available():
        print(MISSING_TERMUX_HELP, file=sys.stderr, flush=True)
        return 3

    queue: list[dict] = []
    sent = 0
    batches = 0
    dropped = 0
    warned_missing: set[str] = set()

    def flush() -> None:
        nonlocal sent, batches, dropped
        if not queue:
            return
        chunk = list(queue)
        try:
            status, body = publish(base_url, chunk, token,
                                   timeout=args.timeout, retries=args.retries)
        except PostError as exc:
            dropped += len(chunk)
            queue.clear()
            log(f"dropped {len(chunk)} sample(s): HTTP {exc.status} {exc}")
            return
        accepted = body.get("accepted", len(chunk))
        rejected = body.get("rejected", 0)
        if isinstance(accepted, bool) or not isinstance(accepted, int) or accepted < 0:
            accepted = len(chunk)
        if isinstance(rejected, bool) or not isinstance(rejected, int) or rejected < 0:
            rejected = max(0, len(chunk) - accepted)
        accepted = min(accepted, len(chunk))
        rejected = min(rejected, len(chunk) - accepted)
        sent += accepted
        dropped += rejected
        batches += 1
        queue.clear()
        if rejected:
            detail = body.get("error") or "server rejected samples"
            log(f"server rejected {rejected} sample(s): {detail}")
        extra = _response_metrics(body)
        log(f"POST {endpoint_for(len(chunk))} {status} "
            f"n={len(chunk)} accepted={accepted} total={sent} " + " ".join(extra))

    try:
        next_at = time.monotonic()
        while True:
            delay = next_at - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            next_at = max(next_at + 1.0 / args.hz, time.monotonic())
            try:
                sample, readings = read_sample(
                    args.sensors, sample_ms,
                    rf_fingerprint=args.rf_fingerprint, learn=args.learn)
            except FileNotFoundError:
                print(MISSING_TERMUX_HELP, file=sys.stderr, flush=True)
                return 3
            except (LineProtocolError, ValueError) as exc:
                log(f"sensor read failed: {exc}")
                return 4
            missing = set(missing_channels(readings))
            new_missing = missing - warned_missing
            if new_missing:
                warned_missing |= new_missing
                log("missing (zeros sent): " + ", ".join(sorted(new_missing)))

            if args.dry_run:
                print(json.dumps(sample, sort_keys=True), flush=True)
            else:
                queue.append(sample)
                if len(queue) >= args.batch:
                    flush()
            if args.once:
                if not args.dry_run:
                    flush()
                    log(f"done: {sent} sample(s) in {batches} POST(s), "
                        f"{dropped} dropped")
                    return 0 if dropped == 0 else 2
                return 0
    except KeyboardInterrupt:
        if not args.dry_run:
            log("interrupted; flushing the partial batch")
            flush()
            log(f"done: {sent} sample(s) in {batches} POST(s), {dropped} dropped")
            return 0 if dropped == 0 else 2
        return 0


_MISSING = object()


def _find_value(payload: object, keys: Iterable[str], depth: int = 0) -> object:
    """Find the first value under any of ``keys`` (recursive)."""
    if depth > 7 or not isinstance(payload, (dict, list)):
        return _MISSING
    if isinstance(payload, dict):
        wanted = {key.lower() for key in keys}
        for key, value in payload.items():
            if str(key).lower() in wanted:
                return value
        for value in payload.values():
            found = _find_value(value, keys, depth + 1)
            if found is not _MISSING:
                return found
    else:
        for value in payload:
            found = _find_value(value, keys, depth + 1)
            if found is not _MISSING:
                return found
    return _MISSING


def _response_metrics(payload: object) -> list[str]:
    """Compact entropy/poincare summary for the progress line.

    The gateway returns ``entropy_sha`` (hex string) and ``poincare_coords``
    (7 floats, possibly null); older or mock servers return numbers.  Both are
    rendered without dumping a whole hash or vector into every log line.
    """
    parts: list[str] = []
    entropy = _find_value(payload, ("entropy_sha", "entropy", "entropy_bits",
                                    "shannon_entropy"))
    if isinstance(entropy, str) and entropy.strip():
        parts.append("entropy=" + entropy.strip()[:12])
    elif isinstance(entropy, (int, float)) and not isinstance(entropy, bool) \
            and math.isfinite(float(entropy)):
        parts.append(f"entropy={float(entropy):.4g}")

    coords = _find_value(payload, ("poincare_coords", "poincare", "poincare_h",
                                   "curvature"))
    if isinstance(coords, (list, tuple)):
        numbers = [float(v) for v in coords
                   if isinstance(v, (int, float)) and not isinstance(v, bool)
                   and math.isfinite(float(v))]
        if numbers:
            head = ",".join(f"{v:.3f}" for v in numbers[:3])
            parts.append(f"poincare=[{head}{',...' if len(numbers) > 3 else ''}]")
    elif isinstance(coords, (int, float)) and not isinstance(coords, bool) \
            and math.isfinite(float(coords)):
        parts.append(f"poincare={float(coords):.4g}")
    elif isinstance(coords, dict) and isinstance(coords.get("h"), (int, float)):
        parts.append(f"poincare.h={float(coords['h']):.4g}")
    return parts


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except PostError as exc:
        log(f"fatal POST error: HTTP {exc.status} {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
