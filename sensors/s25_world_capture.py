#!/usr/bin/env python3
"""Capture Galaxy S25 sensors and camera frames into an ABRASAX world.

This is the Phase 1 phone-side capture client for the world model.  It is the
Termux counterpart of ``UI/abrasax-ui/web/world``: the browser client covers the
same wire contract where Android exposes the APIs, and this script covers the
cases where the browser refuses to (plain ``http://`` is not a secure context).

Wire contract (owned by ``abrasax.gateway`` -- do not change unilaterally)::

    POST /v1/sensors/batch   {"samples": [<sample>, ...]}  1..256 samples
    POST /v1/camera/frame    raw image/jpeg body
    GET  /v1/world/state     read-only verification target
    Authorization: Bearer <ABRASAX_GATEWAY_TOKEN>          when configured

Sample fields::

    kind              "sensor"
    provider_id       default "s25"
    origin            "measured" (this script never emits simulated data)
    seq               producer-local sequence number
    timestamp         wall-clock UTC ISO-8601, for correlation only
    imu               [ax, ay, az, gx, gy, gz]  m/s^2, rad/s
    mag               [mx, my, mz]              microtesla
    env               [pressure_hpa, light_lux]  (omitted when unavailable)
    rf_fingerprint    default "termux-s25-world"

Honesty rules:
  * Only channels that ``termux-sensor`` actually returned are sent.  Missing
    pressure or light omits ``env`` rather than fabricating ``[0, 0]``.
  * A camera frame is uploaded only after ``termux-camera-photo`` produced a
    file whose first bytes are a real JPEG (``FF D8 FF``).
  * No synthetic or interpolated sample is ever labelled measured.

Termux prerequisites::

    pkg update && pkg install termux-api
    # install the matching Termux:API app from the same F-Droid source
    termux-sensor -l
    termux-camera-photo -h

Usage::

    # one batch, no network
    python s25_world_capture.py --once --dry-run

    # stream 10 Hz, 20 samples per POST, camera at 1 fps
    export ABRASAX_GATEWAY_TOKEN=...
    python s25_world_capture.py --base-url http://192.168.1.20:9002 \
        --hz 10 --batch 20 --camera-fps 1

    # through adb reverse (secure-context-friendly on the phone)
    adb reverse tcp:9001 tcp:9001
    python s25_world_capture.py --base-url http://127.0.0.1:9001

Exit codes: 0 ok, 2 configuration/authorisation, 3 termux-sensor missing,
4 sensor read/parse failure, 130 interrupted.

Security: the token is read from an environment variable only.  It is never an
argv value, never written to disk by this script, and never printed.  Logs say
``token=present`` or ``token=absent`` and nothing else.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

VERSION = "1.0.0"

DEFAULT_BASE_URL = "http://127.0.0.1:9001"
DEFAULT_TOKEN_ENV = "ABRASAX_GATEWAY_TOKEN"
DEFAULT_HZ = 10.0
DEFAULT_BATCH = 10
DEFAULT_CAMERA_FPS = 1.0
DEFAULT_CAMERA_ID = "0"
DEFAULT_SENSORS = "accelerometer,gyroscope,magnetometer,pressure,light"
DEFAULT_PROVIDER = "s25"
DEFAULT_RF_FINGERPRINT = "termux-s25-world"
DEFAULT_RETRIES = 4
DEFAULT_TIMEOUT = 10.0
MAX_BATCH = 256

SENSOR_ENV = "ABRASAX_TERMUX_SENSOR"
CAMERA_ENV = "ABRASAX_TERMUX_CAMERA"

BATCH_PATH = "/v1/sensors/batch"
FRAME_PATH = "/v1/camera/frame"

SENSOR_ALIASES: dict[str, tuple[str, ...]] = {
    "accel": ("accelerometer",),
    "gyro": ("gyroscope", "gyro"),
    "mag": ("magnetometer", "magnetic field", "magnetic"),
    "pressure": ("pressure", "barometer"),
    "light": ("light", "lux"),
    "temperature": ("temperature",),
}

# Prefer a calibrated, gravity-included source when the ROM exposes several.
SENSOR_PENALTIES = ("uncalibrated", "linear acceleration", "game rotation")

JPEG_MAGIC = b"\xff\xd8\xff"


class LineProtocolError(RuntimeError):
    """``termux-sensor`` produced something this client cannot interpret."""


class PostError(RuntimeError):
    """A POST failed. ``status`` is 0 for transport failures."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = int(status)


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


def _vector(values: object, length: int) -> list[float] | None:
    """Coerce one sensor reading to ``length`` floats, or None when absent."""
    if values is None:
        return None
    if isinstance(values, (int, float)) and not isinstance(values, bool):
        values = [values]
    if not isinstance(values, (list, tuple)) or not values:
        return None
    out = [_as_float(v, "sensor value") for v in list(values)[:length]]
    return out + [0.0] * (length - len(out))


def _extract_values(node: object) -> list[float] | None:
    """Find the numeric vector inside one termux-sensor entry.

    Known shapes:
      {"values": [1, 2, 3]}
      {"values": [[1, 2, 3]]}          batched single sample
      {"values": [[...], [...]]}       -n > 1; newest sample last
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


def _decode_documents(text: str) -> list[dict]:
    """Parse one or more concatenated JSON objects from termux-sensor."""
    raw = text.strip()
    if not raw:
        raise LineProtocolError("termux-sensor produced no output")
    try:
        parsed = json.loads(raw)
        candidates = parsed if isinstance(parsed, list) else [parsed]
    except ValueError:
        candidates = []
        decoder = json.JSONDecoder()
        index = 0
        while index < len(raw):
            while index < len(raw) and raw[index] in " \t\r\n":
                index += 1
            if index >= len(raw):
                break
            try:
                value, end = decoder.raw_decode(raw, index)
            except ValueError:
                start, stop = raw.find("{", index), raw.rfind("}")
                if start < 0 or stop <= start:
                    raise LineProtocolError(
                        f"termux-sensor output is not JSON: {raw[:160]!r}") from None
                try:
                    candidates.append(json.loads(raw[start:stop + 1]))
                except ValueError:
                    raise LineProtocolError(
                        f"termux-sensor output is not JSON: {raw[:160]!r}") from None
                break
            candidates.append(value)
            index = end
    out = []
    for item in candidates:
        if isinstance(item, dict):
            out.append(item)
    if not out:
        raise LineProtocolError("termux-sensor returned no JSON object")
    return out


def parse_termux_sensor_output(text: str) -> dict[str, list[float]]:
    """Map termux-sensor JSON to canonical channel names.

    The newest sample wins when several documents are present.  Unknown vendor
    channels are ignored instead of failing the read.
    """
    best: dict[str, tuple[int, list[float]]] = {}
    for payload in _decode_documents(text):
        for name, node in payload.items():
            canonical = classify_sensor(str(name))
            if canonical is None:
                continue
            values = _extract_values(node)
            if values is None:
                continue
            rank = _penalty(str(name))
            if canonical not in best or rank <= best[canonical][0]:
                best[canonical] = (rank, values)
    if not best:
        raise LineProtocolError(
            "no accelerometer/gyroscope/magnetometer/pressure/light entry found")
    return {name: values for name, (_rank, values) in best.items()}


def _round(values: Iterable[float], digits: int = 6) -> list[float]:
    return [round(float(v), digits) for v in values]


def build_sample(readings: dict[str, Sequence[float]], *,
                 timestamp: str | None = None,
                 seq: int = 0,
                 origin: str = "measured",
                 provider_id: str = DEFAULT_PROVIDER,
                 sensor_id: str = "phone",
                 rf_fingerprint: str = DEFAULT_RF_FINGERPRINT) -> dict:
    """Build the exact /v1/sensors/batch sample body from channel readings.

    Only channels that are actually present are emitted.  ``env`` requires both
    pressure and light because the gateway contract is ``[hPa, lux]``; a zero
    substitute would be a fabricated reading.
    """
    if origin not in ("measured", "derived", "inferred", "simulated"):
        raise ValueError(f"invalid origin {origin!r}")
    sample: dict = {
        "kind": "sensor",
        "provider_id": str(provider_id)[:64],
        "sensor_id": str(sensor_id)[:64],
        "origin": origin,
        "seq": int(seq),
        "timestamp": timestamp or iso_now(),
    }
    mag = _vector(readings.get("mag"), 3)
    accel = _vector(readings.get("accel"), 3)
    gyro = _vector(readings.get("gyro"), 3)
    if mag is not None:
        sample["mag"] = _round(mag)
    if accel is not None or gyro is not None:
        sample["imu"] = _round((accel or [0.0, 0.0, 0.0]) +
                               (gyro or [0.0, 0.0, 0.0]))
    pressure = _vector(readings.get("pressure"), 1)
    light = _vector(readings.get("light"), 1)
    if pressure is not None and light is not None:
        sample["env"] = _round([pressure[0], light[0]])
    if rf_fingerprint:
        sample["rf_fingerprint"] = str(rf_fingerprint)[:128]
    return sample


def build_batch(samples: object) -> list:
    """Validate the outer batch envelope.  Raises ValueError."""
    if not isinstance(samples, list) or not samples:
        raise ValueError("samples must be a non-empty array")
    if len(samples) > MAX_BATCH:
        raise ValueError(f"batch has {len(samples)} samples; limit is {MAX_BATCH}")
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ValueError(f"samples[{index}] must be an object")
        if sample.get("origin") not in ("measured", "derived", "inferred",
                                        "simulated"):
            raise ValueError(f"samples[{index}].origin is not a valid origin")
    return samples


def dry_run_json(samples: Sequence[dict]) -> str:
    """Deterministic, token-free representation printed by --dry-run."""
    return json.dumps({"samples": build_batch(list(samples))},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ---------------------------------------------------------------------------
# transport
# ---------------------------------------------------------------------------

def _redact(text: object, token: str) -> str:
    out = str(text if text is not None else "")
    if token:
        out = out.replace(token, "[redacted]")
    return out[:400]


def _request_bytes(url: str, data: bytes, content_type: str, token: str,
                   timeout: float) -> tuple[int, dict]:
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(65536)
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        raw = exc.read(400)
        raise PostError(exc.code, _redact(raw.decode("utf-8", "replace"), token))
    except urllib.error.URLError as exc:
        raise PostError(0, _redact(exc.reason, token)) from None
    except OSError as exc:
        raise PostError(0, _redact(exc, token)) from None
    try:
        body = json.loads(raw.decode("utf-8", "replace")) if raw else {}
    except ValueError:
        body = {"raw": raw.decode("utf-8", "replace")[:400]}
    if not isinstance(body, dict):
        body = {"response": body}
    return status, body


def post_json(base_url: str, path: str, payload: dict, token: str, *,
              timeout: float = DEFAULT_TIMEOUT,
              retries: int = DEFAULT_RETRIES) -> tuple[int, dict]:
    """POST one JSON payload with bounded exponential backoff."""
    url = base_url.rstrip("/") + path
    data = json.dumps(payload, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return _post_with_retries(url, data, "application/json", token,
                              timeout=timeout, retries=retries)


def post_frame(base_url: str, jpeg: bytes, token: str, *,
               timeout: float = DEFAULT_TIMEOUT,
               retries: int = DEFAULT_RETRIES) -> tuple[int, dict]:
    """POST one raw JPEG frame with bounded exponential backoff."""
    if not jpeg.startswith(JPEG_MAGIC):
        raise ValueError("frame is not JPEG (missing FF D8 FF)")
    url = base_url.rstrip("/") + FRAME_PATH
    return _post_with_retries(url, jpeg, "image/jpeg", token,
                              timeout=timeout, retries=retries)


def _post_with_retries(url: str, data: bytes, content_type: str, token: str,
                       *, timeout: float, retries: int) -> tuple[int, dict]:
    attempts = max(1, int(retries))
    delay = 0.5
    last: PostError | None = None
    for attempt in range(attempts):
        try:
            return _request_bytes(url, data, content_type, token, timeout)
        except PostError as exc:
            last = exc
            retryable = exc.status == 0 or exc.status == 408 or exc.status == 429 \
                or exc.status >= 500
            if not retryable or attempt == attempts - 1:
                raise
            log(f"POST {url} failed ({exc.status or 'transport'}); "
                f"retry {attempt + 1}/{attempts - 1} in {delay:.1f}s")
            time.sleep(delay)
            delay = min(8.0, delay * 2.0)
    raise last or PostError(0, "POST failed")


# ---------------------------------------------------------------------------
# termux tools
# ---------------------------------------------------------------------------

def termux_sensor_exe() -> str | None:
    override = (os.environ.get(SENSOR_ENV) or "").strip()
    if override:
        return override if os.path.isfile(override) else None
    return shutil.which("termux-sensor")


def termux_camera_exe() -> str | None:
    override = (os.environ.get(CAMERA_ENV) or "").strip()
    if override:
        return override if os.path.isfile(override) else None
    return shutil.which("termux-camera-photo")


MISSING_TERMUX_HELP = """\
termux-sensor not found.

Install Termux:API on the phone from F-Droid (the Play Store build is dead):
  pkg update && pkg install termux-api
Then install the matching "Termux:API" app from the same F-Droid source, open
Termux once, and grant sensor permission when Android asks.
Verify:
  termux-sensor -l
If the binary lives elsewhere:
  export ABRASAX_TERMUX_SENSOR=/data/data/com.termux/files/usr/bin/termux-sensor
"""

MISSING_CAMERA_HELP = """\
termux-camera-photo not found; continuing with sensors only.

Install the Termux:API app from F-Droid and grant camera permission:
  pkg install termux-api
  termux-camera-photo -c 0 /data/data/com.termux/files/home/frame.jpg
To disable camera capture entirely: --camera-fps 0
"""


def read_sensors(sensors: str, sample_ms: int,
                 timeout: float | None = None) -> str:
    """Run one bounded ``termux-sensor -n 1`` call and return stdout."""
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
    except OSError as exc:
        raise LineProtocolError(f"termux-sensor could not start: {exc}") from None
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else f"exit {result.returncode}"
        raise LineProtocolError(f"termux-sensor failed: {tail[:200]}")
    return result.stdout


def read_sample(sensors: str, sample_ms: int, *, seq: int,
                provider_id: str, rf_fingerprint: str) -> tuple[dict, dict]:
    readings = parse_termux_sensor_output(read_sensors(sensors, sample_ms))
    sample = build_sample(readings, seq=seq, provider_id=provider_id,
                          rf_fingerprint=rf_fingerprint)
    return sample, readings


def capture_jpeg(path: Path, camera_id: str = DEFAULT_CAMERA_ID,
                 timeout: float = 15.0) -> bytes:
    """Capture one photo to ``path`` and return the verified JPEG bytes."""
    exe = termux_camera_exe()
    if exe is None:
        raise FileNotFoundError("termux-camera-photo")
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
    command = [exe, "-c", str(camera_id), str(path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout)
    except subprocess.TimeoutExpired:
        raise LineProtocolError(
            f"termux-camera-photo did not answer within {timeout:.1f}s") from None
    except OSError as exc:
        raise LineProtocolError(f"termux-camera-photo could not start: {exc}") from None
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else f"exit {result.returncode}"
        raise LineProtocolError(f"termux-camera-photo failed: {tail[:200]}")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise LineProtocolError(f"camera file unreadable: {exc}") from None
    if not data:
        raise LineProtocolError("termux-camera-photo produced an empty file")
    if not data.startswith(JPEG_MAGIC):
        raise LineProtocolError("termux-camera-photo output is not JPEG")
    return data


# ---------------------------------------------------------------------------
# loops
# ---------------------------------------------------------------------------

def _camera_loop(base_url: str, token: str, fps: float, camera_dir: Path,
                 camera_id: str, stop: threading.Event,
                 timeout: float, retries: int) -> None:
    interval = 1.0 / max(0.1, fps)
    frame = 0
    next_at = time.monotonic()
    while not stop.is_set():
        path = camera_dir / f"frame-{frame:06d}.jpg"
        try:
            data = capture_jpeg(path, camera_id=camera_id,
                                timeout=max(5.0, timeout * 1.5))
            post_frame(base_url, data, token, timeout=timeout, retries=retries)
            frame += 1
            if frame == 1 or frame % 30 == 0:
                log(f"camera frame {frame} accepted ({len(data)} bytes)")
        except FileNotFoundError:
            print(MISSING_CAMERA_HELP, file=sys.stderr, flush=True)
            log("camera disabled; sensors continue")
            return
        except (LineProtocolError, PostError, ValueError) as exc:
            status = getattr(exc, "status", None)
            log(f"camera frame failed: {_redact(exc, token)}")
            if status == 401:
                log("401 unauthorized: check the token environment variable")
                stop.set()
                return
        finally:
            try:
                path.unlink()
            except OSError:
                pass
        next_at += interval
        wait = next_at - time.monotonic()
        if wait > 0:
            stop.wait(wait)
        else:
            next_at = time.monotonic()


def _flush(base_url: str, queue: list[dict], token: str, *, dry_run: bool,
           timeout: float, retries: int, counters: dict) -> None:
    if not queue:
        return
    chunk = list(queue)
    if dry_run:
        print(dry_run_json(chunk), flush=True)
        counters["sent"] += len(chunk)
        counters["batches"] += 1
        queue.clear()
        return
    try:
        status, body = post_json(base_url, BATCH_PATH, {"samples": chunk},
                                 token, timeout=timeout, retries=retries)
    except PostError as exc:
        counters["dropped"] += len(chunk)
        queue.clear()
        log(f"dropped {len(chunk)} sample(s): HTTP {exc.status or 'transport'} "
            f"{_redact(exc, token)}")
        return
    accepted = body.get("accepted", len(chunk))
    rejected = body.get("rejected", 0)
    if isinstance(accepted, bool) or not isinstance(accepted, int):
        accepted = len(chunk)
    if isinstance(rejected, bool) or not isinstance(rejected, int):
        rejected = 0
    accepted = max(0, min(accepted, len(chunk)))
    counters["sent"] += accepted
    counters["dropped"] += max(0, min(rejected, len(chunk) - accepted))
    counters["batches"] += 1
    queue.clear()
    log(f"POST {BATCH_PATH} {status} n={len(chunk)} accepted={accepted} "
        f"total={counters['sent']}")


def _capture_once(base_url: str, token: str, args: argparse.Namespace,
                  queue: list[dict], counters: dict) -> int:
    for seq in range(1):
        try:
            sample, readings = read_sample(
                args.sensors, int(round(1000.0 / args.hz)), seq=seq,
                provider_id=args.provider_id,
                rf_fingerprint=args.rf_fingerprint)
        except FileNotFoundError:
            print(MISSING_TERMUX_HELP, file=sys.stderr, flush=True)
            return 3
        except LineProtocolError as exc:
            log(f"sensor read failed: {exc}")
            return 4
        queue.append(sample)
        log("sensor channels: " + ", ".join(sorted(readings)))
    _flush(base_url, queue, token, dry_run=args.dry_run,
           timeout=args.timeout, retries=args.retries, counters=counters)
    if args.dry_run or args.camera_fps <= 0:
        return 0
    if termux_camera_exe() is None:
        print(MISSING_CAMERA_HELP, file=sys.stderr, flush=True)
        return 0
    camera_dir = Path(args.camera_dir)
    camera_dir.mkdir(parents=True, exist_ok=True)
    path = camera_dir / "frame-once.jpg"
    try:
        data = capture_jpeg(path, camera_id=args.camera_id,
                            timeout=max(5.0, args.timeout * 1.5))
        post_frame(base_url, data, token, timeout=args.timeout,
                   retries=args.retries)
        log(f"camera frame accepted ({len(data)} bytes)")
        return 0
    except (LineProtocolError, PostError, ValueError) as exc:
        log(f"camera frame failed: {_redact(exc, token)}")
        return 0
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def _run(args: argparse.Namespace) -> int:
    _validate_args(args)
    token = (os.environ.get(args.token_env) or "").strip()
    base_url = args.base_url.rstrip("/")
    sample_ms = max(1, int(round(1000.0 / args.hz)))
    counters = {"sent": 0, "dropped": 0, "batches": 0}

    if not args.dry_run:
        log(f"gateway {base_url}  token={'present' if token else 'absent'}  "
            f"hz={args.hz:g}  batch={args.batch}  camera={args.camera_fps:g} fps")
        if not token:
            log(f"{args.token_env} is unset; an open gateway accepts it, a "
                "token gateway answers 401")

    if termux_sensor_exe() is None:
        print(MISSING_TERMUX_HELP, file=sys.stderr, flush=True)
        return 3

    queue: list[dict] = []
    if args.once:
        return _capture_once(base_url, token, args, queue, counters)

    camera_stop = threading.Event()
    camera_thread = None
    camera_dir = Path(args.camera_dir)
    if args.camera_fps > 0 and not args.dry_run:
        if termux_camera_exe() is None:
            print(MISSING_CAMERA_HELP, file=sys.stderr, flush=True)
            log("camera disabled; sensors continue")
        else:
            camera_dir.mkdir(parents=True, exist_ok=True)
            camera_thread = threading.Thread(
                target=_camera_loop,
                args=(base_url, token, args.camera_fps, camera_dir,
                      args.camera_id, camera_stop, args.timeout, args.retries),
                name="camera", daemon=True)
            camera_thread.start()

    seq = 0
    next_at = time.monotonic()
    try:
        while True:
            try:
                sample, readings = read_sample(
                    args.sensors, sample_ms, seq=seq,
                    provider_id=args.provider_id,
                    rf_fingerprint=args.rf_fingerprint)
                queue.append(sample)
                seq += 1
                if seq == 1:
                    log("sensor channels: " + ", ".join(sorted(readings)))
                if len(queue) >= args.batch:
                    _flush(base_url, queue, token, dry_run=args.dry_run,
                           timeout=args.timeout, retries=args.retries,
                           counters=counters)
            except FileNotFoundError:
                print(MISSING_TERMUX_HELP, file=sys.stderr, flush=True)
                return 3
            except LineProtocolError as exc:
                log(f"sensor read failed: {exc}")
                if counters["sent"] == 0 and seq == 0:
                    return 4
            next_at += 1.0 / args.hz
            wait = next_at - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            else:
                next_at = time.monotonic()
    except KeyboardInterrupt:
        log("interrupted; flushing queued samples")
        _flush(base_url, queue, token, dry_run=args.dry_run,
               timeout=args.timeout, retries=args.retries, counters=counters)
        return 130
    finally:
        camera_stop.set()
        if camera_thread is not None:
            camera_thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="s25_world_capture.py",
        description="Capture S25 sensors and camera frames into the ABRASAX world.",
        epilog="The token is read from an environment variable, never argv.")
    parser.add_argument("--base-url",
                        default=os.environ.get("ABRASAX_GATEWAY_URL", DEFAULT_BASE_URL),
                        help=f"gateway origin (default {DEFAULT_BASE_URL})")
    parser.add_argument("--token-env", default=DEFAULT_TOKEN_ENV,
                        help=f"env var holding the bearer token (default {DEFAULT_TOKEN_ENV})")
    parser.add_argument("--hz", type=float, default=DEFAULT_HZ,
                        help=f"sensor samples per second (default {DEFAULT_HZ:g})")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH,
                        help=f"samples per POST, 1-{MAX_BATCH} (default {DEFAULT_BATCH})")
    parser.add_argument("--camera-fps", type=float, default=DEFAULT_CAMERA_FPS,
                        help=f"camera frames per second, 0 disables (default {DEFAULT_CAMERA_FPS:g})")
    parser.add_argument("--camera-dir", default=os.environ.get("ABRASAX_CAMERA_TMP")
                        or tempfile.gettempdir(),
                        help="directory for the transient JPEG before upload")
    parser.add_argument("--camera-id", default=DEFAULT_CAMERA_ID,
                        help=f"termux-camera-photo -c value (default {DEFAULT_CAMERA_ID})")
    parser.add_argument("--sensors", default=DEFAULT_SENSORS,
                        help=f"comma-separated termux-sensor names (default {DEFAULT_SENSORS})")
    parser.add_argument("--provider-id", default=DEFAULT_PROVIDER,
                        help=f"provider_id field (default {DEFAULT_PROVIDER})")
    parser.add_argument("--rf-fingerprint", default=DEFAULT_RF_FINGERPRINT,
                        help=f"rf_fingerprint field (default {DEFAULT_RF_FINGERPRINT})")
    parser.add_argument("--once", action="store_true",
                        help="send one sensor sample (and one frame) then exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="print payloads to stdout, never touch the network")
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
    if not (0.0 <= args.camera_fps <= 30.0):
        raise SystemExit(f"--camera-fps must be between 0 and 30, got {args.camera_fps}")
    if args.retries < 1:
        raise SystemExit(f"--retries must be >= 1, got {args.retries}")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be > 0")
    if not args.base_url.startswith(("http://", "https://")):
        raise SystemExit("--base-url must start with http:// or https://")
    if not args.sensors.strip():
        raise SystemExit("--sensors must not be empty")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
