#!/usr/bin/env python3
"""ABRASAX-NEO — a real GGUF v3 reader and a minimal float32 transformer.

This module does not depend on ``abrasax`` or on any third-party GGUF library.
It parses the container with :mod:`struct` (little-endian, GGUF v2/v3),
validates every tensor offset and byte length against the file size, and runs
the declared architecture (RMSNorm -> RoPE causal attention -> SwiGLU) in numpy
``float32``.

Container facts for ``MODELS/gguf/ABRASAX-NEO.gguf`` (measured, not assumed)::

    magic  'GGUF'   version 3   tensor_count 21   kv_count 16
    tensor infos end at 2017 -> align 32 -> tensor data at 2048
    payload 787712 bytes -> 2048 + 787712 == 789760 == file size (trailing 0)
    all 21 tensors are ggml type 0 (F32); 196928 parameters

FAIL-LOUD POLICY
----------------
* bad magic / unsupported version / truncated header  -> GGUFBadMagic,
  GGUFVersionError, GGUFTruncated
* a tensor whose ``[offset, offset+nbytes)`` leaves the data region
  -> GGUFTruncated naming the tensor and the missing byte range
* overlapping tensors, unaccounted gaps, or trailing bytes in strict mode
  -> GGUFError
* unknown ggml type -> UnsupportedGGMLType when the tensor is touched (the
  reader can still describe the file, ``nbytes`` is reported as ``None``)
* non-finite weights or logits -> NeoNumericalError

Nothing here silently clamps, skips, or guesses a byte layout.

API
---
``GGUFReader(path)``        container: ``.metadata``, ``.tensors``, ``.tensor(name)``
``ByteTokenizer(vocab)``    ids 0-255 are literal bytes; 256 <bos>, 257 <eos>
``NeoModel(reader)``        ``.forward(ids) -> (T, vocab) logits``, ``.generate(...)``
``load_neo(path)``          convenience: reader + model

CLI: ``python SCRIPTS/tools/neo_infer.py --prompt "hello world" --tokens 16``
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

__all__ = [
    "GGUF_MAGIC",
    "GGUFError",
    "GGUFBadMagic",
    "GGUFVersionError",
    "GGUFTruncated",
    "UnsupportedGGMLType",
    "NeoShapeError",
    "NeoNumericalError",
    "TensorInfo",
    "GGUFReader",
    "ByteTokenizer",
    "NeoConfig",
    "NeoModel",
    "load_neo",
    "expand_kv_heads",
    "DEFAULT_GGUF",
]

GGUF_MAGIC = b"GGUF"
SUPPORTED_VERSIONS = (2, 3)          # the NEO checkpoint is v3
DEFAULT_ALIGNMENT = 32               # gguf spec: general.alignment defaults to 32
NORM_EPS_DEFAULT = 1e-5              # llama-family RMSNorm epsilon
BOS_ID, EOS_ID = 256, 257
DEFAULT_GGUF = Path("C:/ABRASAX/MODELS/gguf/ABRASAX-NEO.gguf")


# --------------------------------------------------------------------------- #
# errors
# --------------------------------------------------------------------------- #
class GGUFError(Exception):
    """Base class for every container/model error raised by this module."""


class GGUFBadMagic(GGUFError):
    """The first four bytes are not ``GGUF``."""


class GGUFVersionError(GGUFError):
    """Unsupported GGUF version (v1 is refused: different header layout)."""


class GGUFTruncated(GGUFError):
    """A read ran past the end of the file, or a tensor does not fit."""


class UnsupportedGGMLType(GGUFError):
    """A ggml tensor type whose block layout is not implemented here."""


class NeoShapeError(GGUFError):
    """A tensor shape contradicts the architecture declared in the metadata."""


class NeoNumericalError(GGUFError):
    """Weights or logits contain NaN/Inf."""


# --------------------------------------------------------------------------- #
# gguf scalar types
# --------------------------------------------------------------------------- #
# id -> (name, struct format, size)
GGUF_META_TYPES: Dict[int, Tuple[str, str, int]] = {
    0: ("UINT8", "<B", 1),
    1: ("INT8", "<b", 1),
    2: ("UINT16", "<H", 2),
    3: ("INT16", "<h", 2),
    4: ("UINT32", "<I", 4),
    5: ("INT32", "<i", 4),
    6: ("FLOAT32", "<f", 4),
    7: ("BOOL", "<B", 1),
    8: ("STRING", "", 0),
    9: ("ARRAY", "", 0),
    10: ("UINT64", "<Q", 8),
    11: ("INT64", "<q", 8),
    12: ("FLOAT64", "<d", 8),
}


@dataclass(frozen=True)
class GGMLTypeSpec:
    name: str
    block_elems: int
    block_bytes: int
    decodable: bool


# Sizes follow ggml.c's type_traits table. ``decodable`` marks the layouts this
# loader actually dequantises; everything else is refused, never guessed.
GGML_TYPES: Dict[int, GGMLTypeSpec] = {
    0: GGMLTypeSpec("F32", 1, 4, True),
    1: GGMLTypeSpec("F16", 1, 2, True),
    2: GGMLTypeSpec("Q4_0", 32, 18, False),
    3: GGMLTypeSpec("Q4_1", 32, 20, False),
    6: GGMLTypeSpec("Q5_0", 32, 22, False),
    7: GGMLTypeSpec("Q5_1", 32, 24, False),
    8: GGMLTypeSpec("Q8_0", 32, 34, True),
    9: GGMLTypeSpec("Q8_1", 32, 40, False),
    10: GGMLTypeSpec("Q2_K", 256, 84, False),
    11: GGMLTypeSpec("Q3_K", 256, 110, False),
    12: GGMLTypeSpec("Q4_K", 256, 144, False),
    13: GGMLTypeSpec("Q5_K", 256, 176, False),
    14: GGMLTypeSpec("Q6_K", 256, 210, False),
    15: GGMLTypeSpec("Q8_K", 256, 292, False),
    24: GGMLTypeSpec("I8", 1, 1, False),
    25: GGMLTypeSpec("I16", 1, 2, False),
    26: GGMLTypeSpec("I32", 1, 4, False),
    27: GGMLTypeSpec("I64", 1, 8, False),
    28: GGMLTypeSpec("F64", 1, 8, False),
    30: GGMLTypeSpec("BF16", 1, 2, True),
}


def ggml_type_name(tid: int) -> str:
    spec = GGML_TYPES.get(tid)
    return spec.name if spec else "UNKNOWN_%d" % tid


def align_up(value: int, alignment: int) -> int:
    if alignment <= 0 or (alignment & (alignment - 1)) != 0:
        raise GGUFError("alignment must be a positive power of two, got %r" % (alignment,))
    return (value + alignment - 1) // alignment * alignment


# --------------------------------------------------------------------------- #
# bounded cursor: every read is checked against the file, no silent short reads
# --------------------------------------------------------------------------- #
class _Cursor:
    __slots__ = ("buf", "pos", "limit")

    def __init__(self, buf: bytes):
        self.buf = buf
        self.pos = 0
        self.limit = len(buf)

    @property
    def remaining(self) -> int:
        return self.limit - self.pos

    def take(self, n: int, what: str) -> bytes:
        if n < 0:
            raise GGUFTruncated("%s: negative length %d" % (what, n))
        end = self.pos + n
        if end > self.limit:
            raise GGUFTruncated(
                "%s: need %d bytes at offset %d but the file ends at %d "
                "(short by %d)" % (what, n, self.pos, self.limit, end - self.limit)
            )
        out = self.buf[self.pos:end]
        self.pos = end
        return out

    def unpack(self, fmt: str, what: str) -> Any:
        st = struct.Struct(fmt)
        return st.unpack(self.take(st.size, what))[0]

    def u32(self, what: str) -> int:
        return self.unpack("<I", what)

    def u64(self, what: str) -> int:
        return self.unpack("<Q", what)

    def string(self, what: str) -> str:
        n = self.u64(what + " [length]")
        if n > self.remaining:
            raise GGUFTruncated(
                "%s: string length %d at offset %d exceeds the %d remaining bytes"
                % (what, n, self.pos, self.remaining)
            )
        raw = self.take(n, what)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GGUFError("%s: not valid UTF-8 (%s)" % (what, exc)) from exc


def _read_meta_value(cur: _Cursor, vtype: int, key: str) -> Any:
    if vtype == 8:                                   # string
        return cur.string("metadata %r" % key)
    if vtype == 9:                                   # array (possible nesting)
        etype = cur.u32("metadata %r array element type" % key)
        count = cur.u64("metadata %r array length" % key)
        if count > cur.remaining:
            raise GGUFTruncated(
                "metadata %r: array of %d elements cannot fit in %d remaining bytes"
                % (key, count, cur.remaining)
            )
        return [_read_meta_value(cur, etype, "%s[%d]" % (key, i)) for i in range(count)]
    spec = GGUF_META_TYPES.get(vtype)
    if spec is None:
        raise GGUFError("metadata %r: unknown value type %d" % (key, vtype))
    name, fmt, _size = spec
    val = cur.unpack(fmt, "metadata %r (%s)" % (key, name))
    return bool(val) if vtype == 7 else val


# --------------------------------------------------------------------------- #
# tensor table
# --------------------------------------------------------------------------- #
@dataclass
class TensorInfo:
    name: str
    dims: Tuple[int, ...]        # ggml ne[] order: ne[0] is the innermost dim
    ggml_type: int
    offset: int                  # relative to tensor_data_offset
    nbytes: Optional[int]        # None when the type is unknown
    index: int = 0

    @property
    def type_name(self) -> str:
        return ggml_type_name(self.ggml_type)

    @property
    def shape(self) -> Tuple[int, ...]:
        """numpy shape: ggml ne[] reversed, so ne=[64,512] -> (512, 64)."""
        return tuple(reversed(self.dims))

    @property
    def numel(self) -> int:
        n = 1
        for d in self.dims:
            n *= int(d)
        return n

    @property
    def end(self) -> Optional[int]:
        return None if self.nbytes is None else self.offset + self.nbytes

    def as_dict(self, data_start: int) -> Dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "type": self.type_name,
            "ggml_type": self.ggml_type,
            "ne": list(self.dims),
            "shape": list(self.shape),
            "numel": self.numel,
            "offset": self.offset,
            "nbytes": self.nbytes,
            "file_range": None if self.nbytes is None else [data_start + self.offset, data_start + self.end],
        }


class GGUFReader:
    """A GGUF v2/v3 container reader with hard bounds checking."""

    def __init__(self, path: str | Path, *, strict: bool = True):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError("GGUF not found: %s" % self.path)
        self._data = self.path.read_bytes()
        self.size = len(self._data)
        self.strict = bool(strict)
        self.metadata: Dict[str, Any] = {}
        self.kv_types: Dict[str, str] = {}
        self.tensors: Dict[str, TensorInfo] = {}
        self.tensor_list: List[TensorInfo] = []
        self.version = 0
        self.tensor_count = 0
        self.kv_count = 0
        self.header_bytes = 0
        self.alignment = DEFAULT_ALIGNMENT
        self.tensor_data_offset = 0
        self.tensor_data_size = 0
        self.trailing_bytes = 0
        self.gaps: List[Tuple[int, int]] = []
        self.unsupported_types: List[str] = []
        self._parse()

    # -- parsing ----------------------------------------------------------- #
    def _parse(self) -> None:
        cur = _Cursor(self._data)
        magic = cur.take(4, "magic")
        if magic != GGUF_MAGIC:
            raise GGUFBadMagic(
                "%s: bad magic %r (expected b'GGUF' = 47 47 55 46); this is not a "
                "GGUF container" % (self.path, magic)
            )
        self.version = cur.u32("version")
        if self.version not in SUPPORTED_VERSIONS:
            raise GGUFVersionError(
                "%s: GGUF version %d is not supported (accepted: %s; v1 has a "
                "different layout and big-endian files are refused)"
                % (self.path, self.version, ", ".join(str(v) for v in SUPPORTED_VERSIONS))
            )
        self.tensor_count = cur.u64("tensor_count")
        self.kv_count = cur.u64("kv_count")

        # absurd counts would otherwise turn into huge loops before failing
        if self.kv_count > self.size // 12:
            raise GGUFTruncated(
                "kv_count %d cannot fit in a %d-byte file" % (self.kv_count, self.size)
            )
        if self.tensor_count > self.size // 16:
            raise GGUFTruncated(
                "tensor_count %d cannot fit in a %d-byte file" % (self.tensor_count, self.size)
            )

        for i in range(self.kv_count):
            key = cur.string("kv[%d] key" % i)
            vtype = cur.u32("kv[%r] type" % key)
            if key in self.metadata:
                raise GGUFError("duplicate metadata key %r" % key)
            self.metadata[key] = _read_meta_value(cur, vtype, key)
            self.kv_types[key] = GGUF_META_TYPES.get(vtype, ("UNKNOWN_%d" % vtype, "", 0))[0]

        for i in range(self.tensor_count):
            name = cur.string("tensor[%d] name" % i)
            if not name:
                raise GGUFError("tensor[%d] has an empty name" % i)
            if name in self.tensors:
                raise GGUFError("duplicate tensor name %r" % name)
            n_dims = cur.u32("tensor %r n_dims" % name)
            if not 1 <= n_dims <= 8:
                raise GGUFError("tensor %r: n_dims=%d outside 1..8" % (name, n_dims))
            dims = tuple(cur.u64("tensor %r ne[%d]" % (name, d)) for d in range(n_dims))
            if any(d == 0 for d in dims):
                raise GGUFError("tensor %r: zero-sized dimension %r" % (name, dims))
            tid = cur.u32("tensor %r type" % name)
            offset = cur.u64("tensor %r offset" % name)
            spec = GGML_TYPES.get(tid)
            nbytes: Optional[int] = None
            if spec is not None:
                n = 1
                for d in dims:
                    n *= int(d)
                if n % spec.block_elems:
                    raise GGUFError(
                        "tensor %r: %d elements is not a multiple of the %s block "
                        "size %d" % (name, n, spec.name, spec.block_elems)
                    )
                nbytes = n // spec.block_elems * spec.block_bytes
            info = TensorInfo(name=name, dims=dims, ggml_type=tid, offset=offset,
                              nbytes=nbytes, index=i)
            self.tensors[name] = info
            self.tensor_list.append(info)

        infos_end = cur.pos
        self.header_bytes = infos_end
        alignment = self.metadata.get("general.alignment", DEFAULT_ALIGNMENT)
        if not isinstance(alignment, int) or isinstance(alignment, bool) or alignment <= 0:
            raise GGUFError("general.alignment must be a positive integer, got %r"
                            % (alignment,))
        if alignment & (alignment - 1):
            raise GGUFError("general.alignment must be a power of two, got %r" % (alignment,))
        self.alignment = int(alignment)
        self.tensor_data_offset = align_up(infos_end, self.alignment)
        if self.tensor_data_offset > self.size:
            raise GGUFTruncated(
                "tensor data would start at %d but the file is %d bytes"
                % (self.tensor_data_offset, self.size)
            )
        self.tensor_data_size = self.size - self.tensor_data_offset
        self._validate_tensors()

    def _validate_tensors(self) -> None:
        dsize = self.tensor_data_size
        unknown: List[str] = []
        for info in self.tensor_list:
            if info.nbytes is None:
                unknown.append(info.name)
                self.unsupported_types.append(info.name)
                continue
            if info.offset + info.nbytes > dsize:
                raise GGUFTruncated(
                    "tensor %r: bytes [%d, %d) are outside the tensor data region "
                    "[0, %d) (file %d, data_start %d); short by %d bytes"
                    % (info.name, info.offset, info.offset + info.nbytes, dsize,
                       self.size, self.tensor_data_offset,
                       info.offset + info.nbytes - dsize)
                )
        known = sorted((t for t in self.tensor_list if t.nbytes is not None),
                       key=lambda t: t.offset)
        prev_end = 0
        for info in known:
            if info.offset < prev_end:
                raise GGUFError(
                    "tensor %r: offset %d overlaps the previous tensor which ends at %d"
                    % (info.name, info.offset, prev_end)
                )
            if info.offset > prev_end:
                self.gaps.append((prev_end, info.offset))
            prev_end = max(prev_end, info.offset + (info.nbytes or 0))
        max_end = prev_end
        self.trailing_bytes = dsize - max_end if known else dsize
        if self.strict:
            for start, end in self.gaps:
                if end - start > self.alignment:
                    raise GGUFError(
                        "unaccounted gap [%d, %d) of %d bytes in the tensor data "
                        "region (alignment %d); a corrupted offset is the likely "
                        "cause" % (start, end, end - start, self.alignment)
                    )
            if known and known[0].offset != 0:
                raise GGUFError(
                    "first tensor starts at %d, not 0; the tensor table is "
                    "inconsistent with the data region" % known[0].offset
                )
            if self.trailing_bytes > self.alignment:
                raise GGUFError(
                    "%d trailing bytes after the last tensor (alignment %d); "
                    "offsets or lengths do not describe this file"
                    % (self.trailing_bytes, self.alignment)
                )
        self.param_count = sum(t.numel for t in self.tensor_list)
        self.tensor_bytes = sum(t.nbytes or 0 for t in self.tensor_list)
        self.unknown_types = unknown

    # -- access ------------------------------------------------------------ #
    def raw_range(self, start: int, nbytes: int) -> bytes:
        """Read absolute file bytes, refusing any range outside the file."""
        if start < 0 or nbytes < 0 or start + nbytes > self.size:
            raise GGUFTruncated(
                "raw read [%d, %d) outside the %d-byte file" % (start, start + nbytes, self.size)
            )
        return self._data[start:start + nbytes]

    def tensor_raw(self, name: str) -> bytes:
        info = self._info(name)
        if info.nbytes is None:
            raise UnsupportedGGMLType(self._unsupported_msg(info))
        start = self.tensor_data_offset + info.offset
        return self.raw_range(start, info.nbytes)

    def tensor(self, name: str, *, copy: bool = True) -> np.ndarray:
        """Return the tensor as float32 with numpy shape ``reversed(ne)``."""
        info = self._info(name)
        if info.nbytes is None:
            raise UnsupportedGGMLType(self._unsupported_msg(info))
        raw = self.tensor_raw(name)
        arr = self._decode(info, raw)
        if arr.size != info.numel:
            raise GGUFError(
                "tensor %r: decoded %d values, table says %d" % (name, arr.size, info.numel)
            )
        arr = arr.reshape(info.shape).astype(np.float32, copy=False)
        if not np.isfinite(arr).all():
            raise NeoNumericalError("tensor %r contains NaN/Inf" % name)
        return np.array(arr, dtype=np.float32, copy=True) if copy else arr

    def _info(self, name: str) -> TensorInfo:
        try:
            return self.tensors[name]
        except KeyError:
            raise GGUFError("tensor %r is not in this file (have: %s)"
                            % (name, ", ".join(t.name for t in self.tensor_list[:6]) + ", ...")) from None

    @staticmethod
    def _unsupported_msg(info: TensorInfo) -> str:
        return ("tensor %r uses ggml type %d (%s); this loader decodes only "
                "F32/F16/BF16/Q8_0 and refuses to guess a block layout"
                % (info.name, info.ggml_type, info.type_name))

    def _decode(self, info: TensorInfo, raw: bytes) -> np.ndarray:
        tid = info.ggml_type
        if tid == 0:                                       # F32
            return np.frombuffer(raw, dtype="<f4").astype(np.float32, copy=False)
        if tid == 1:                                       # F16
            return np.frombuffer(raw, dtype="<f2").astype(np.float32)
        if tid == 30:                                      # BF16
            u = np.frombuffer(raw, dtype="<u2").astype(np.uint32) << 16
            return u.view(np.float32).copy()
        if tid == 8:                                       # Q8_0: 32 vals / 34 B
            nblocks = info.numel // 32
            dt = np.dtype([("d", "<f2"), ("qs", "i1", (32,))])
            blocks = np.frombuffer(raw, dtype=dt, count=nblocks)
            if blocks.size != nblocks:
                raise GGUFTruncated("tensor %r: Q8_0 block count mismatch" % info.name)
            scale = blocks["d"].astype(np.float32)[:, None]
            return (scale * blocks["qs"].astype(np.float32)).reshape(-1)
        raise UnsupportedGGMLType(self._unsupported_msg(info))

    def header(self) -> Dict[str, Any]:
        return {
            "magic": GGUF_MAGIC.decode("ascii"),
            "version": self.version,
            "tensor_count": self.tensor_count,
            "kv_count": self.kv_count,
            "header_bytes": self.header_bytes,
            "alignment": self.alignment,
            "tensor_data_offset": self.tensor_data_offset,
            "tensor_data_size": self.tensor_data_size,
            "file_bytes": self.size,
            "trailing_bytes": self.trailing_bytes,
            "gaps": [list(g) for g in self.gaps],
        }

    def info(self) -> Dict[str, Any]:
        return {
            "path": str(self.path),
            "file_bytes": self.size,
            "sha256": hashlib.sha256(self._data).hexdigest(),
            "header": self.header(),
            "metadata": dict(self.metadata),
            "metadata_types": dict(self.kv_types),
            "param_count": self.param_count,
            "tensor_bytes": self.tensor_bytes,
            "tensor_count": len(self.tensor_list),
            "type_histogram": self._type_histogram(),
            "unsupported_types": list(self.unsupported_types),
            "tensors": [t.as_dict(self.tensor_data_offset) for t in self.tensor_list],
        }

    def _type_histogram(self) -> Dict[str, int]:
        hist: Dict[str, int] = {}
        for t in self.tensor_list:
            hist[t.type_name] = hist.get(t.type_name, 0) + 1
        return hist

    def describe(self) -> str:
        h = self.header()
        lines = [
            "file      : %s (%d bytes)" % (self.path, self.size),
            "sha256    : %s" % hashlib.sha256(self._data).hexdigest(),
            "header    : magic=%s version=%d tensors=%d kv=%d" % (
                h["magic"], h["version"], h["tensor_count"], h["kv_count"]),
            "alignment : %d  tensor_data_offset=%d  payload=%d  trailing=%d  gaps=%s" % (
                self.alignment, self.tensor_data_offset, self.tensor_data_size,
                self.trailing_bytes, self.gaps or "[]"),
            "params    : %d  tensor types=%s" % (self.param_count, self._type_histogram()),
        ]
        return "\n".join(lines)

    def tensor_table(self) -> str:
        rows = ["  #  %-26s %-5s %-16s %-14s %9s %9s  %s" % (
            "name", "type", "ne", "shape", "offset", "nbytes", "byte range")]
        for t in self.tensor_list:
            rng = "-" if t.nbytes is None else "[%d, %d)" % (
                self.tensor_data_offset + t.offset, self.tensor_data_offset + t.end)
            rows.append("  %2d  %-26s %-5s %-16s %-14s %9d %9s  %s" % (
                t.index, t.name, t.type_name, str(list(t.dims)), str(list(t.shape)),
                t.offset, t.nbytes if t.nbytes is not None else "?", rng))
        return "\n".join(rows)


# --------------------------------------------------------------------------- #
# tokenizer
# --------------------------------------------------------------------------- #
class ByteTokenizer:
    """Byte vocabulary: ids 0-255 are literal bytes, 256 <bos>, 257 <eos>.

    The checkpoint declares no tokenizer (``tokenizer.ggml.model`` is absent),
    so any sub-word vocabulary would be an invention. Encoding is UTF-8 bytes
    reduced modulo ``vocab_size``; decoding concatenates bytes and then decodes
    UTF-8 with ``errors='replace'``.
    """

    def __init__(self, vocab_size: int):
        if vocab_size < 256:
            raise GGUFError("byte tokenizer needs vocab_size >= 256, got %d" % vocab_size)
        self.vocab_size = int(vocab_size)
        self.bos = BOS_ID if self.vocab_size > BOS_ID else None
        self.eos = EOS_ID if self.vocab_size > EOS_ID else None

    def encode(self, text: str, *, add_bos: bool = False) -> List[int]:
        ids = [b % self.vocab_size for b in text.encode("utf-8")]
        if add_bos and self.bos is not None:
            ids = [self.bos] + ids
        return ids

    def decode(self, ids: Iterable[int]) -> str:
        raw = bytes((int(i) % 256) for i in ids if 0 <= int(i) < 256)
        return raw.decode("utf-8", errors="replace")

    def token_text(self, tid: int) -> str:
        if tid < 256:
            return bytes([tid]).decode("utf-8", errors="backslashreplace")
        return "<bos>" if tid == BOS_ID else ("<eos>" if tid == EOS_ID else "<unused_%d>" % tid)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return "ByteTokenizer(vocab=%d, bos=%r, eos=%r)" % (self.vocab_size, self.bos, self.eos)


# --------------------------------------------------------------------------- #
# model
# --------------------------------------------------------------------------- #
@dataclass
class NeoConfig:
    vocab_size: int
    n_embd: int
    n_layer: int
    n_head: int
    n_head_kv: int
    ffn_length: int
    context_length: int
    rope_freq_base: float
    norm_eps: float
    activation: str = "swiglu"
    norm: str = "rmsnorm"
    rope_style: str = "rotate-half (llama/GGUF interleaved pairs i, i+head_dim/2)"

    @property
    def head_dim(self) -> int:
        return self.n_embd // self.n_head

    def as_dict(self) -> Dict[str, Any]:
        return {
            "vocab_size": self.vocab_size,
            "n_embd": self.n_embd,
            "n_layer": self.n_layer,
            "n_head": self.n_head,
            "n_head_kv": self.n_head_kv,
            "head_dim": self.head_dim,
            "ffn_length": self.ffn_length,
            "context_length": self.context_length,
            "rope_freq_base": self.rope_freq_base,
            "norm": self.norm,
            "norm_eps": self.norm_eps,
            "activation": self.activation,
            "rope_style": self.rope_style,
        }


def _expect(shape: Sequence[int], expected: Sequence[int], stage: str) -> None:
    if tuple(int(x) for x in shape) != tuple(int(x) for x in expected):
        raise NeoShapeError("stage %s: shape %r != expected %r"
                            % (stage, tuple(shape), tuple(expected)))


def _finite(name: str, arr: np.ndarray) -> np.ndarray:
    if not np.isfinite(arr).all():
        bad = int(arr.size - np.isfinite(arr).sum())
        raise NeoNumericalError("%s: %d non-finite values (NaN/Inf)" % (name, bad))
    return arr


def rms_norm(x: np.ndarray, weight: np.ndarray, eps: float) -> np.ndarray:
    """RMSNorm over the last axis; weight is the per-channel gain."""
    x = np.asarray(x, dtype=np.float32)
    var = np.mean(np.square(x, dtype=np.float32), axis=-1, keepdims=True, dtype=np.float32)
    return (x / np.sqrt(var + np.float32(eps))) * weight.astype(np.float32)


def silu(x: np.ndarray) -> np.ndarray:
    """SiLU in the tanh form: 0.5x(1+tanh(x/2)), exactly equal and overflow-free."""
    x = np.asarray(x, dtype=np.float32)
    return (np.float32(0.5) * x * (np.float32(1.0) + np.tanh(np.float32(0.5) * x))).astype(np.float32)


def softmax(x: np.ndarray) -> np.ndarray:
    m = np.max(x, axis=-1, keepdims=True)
    e = np.exp(x - m)
    s = np.sum(e, axis=-1, keepdims=True)
    return e / s


def expand_kv_heads(x: np.ndarray, n_head: int, n_head_kv: int) -> np.ndarray:
    """Broadcast key/value heads to the query-head count.

    ``x`` is (T, n_head_kv, head_dim). llama.cpp's GQA mapping is
    ``query head h -> kv head h // (n_head // n_head_kv)``, which is exactly
    ``np.repeat(..., reps, axis=1)``.
    """
    if n_head_kv <= 0 or n_head % n_head_kv:
        raise NeoShapeError("n_head %d is not divisible by n_head_kv %d"
                            % (n_head, n_head_kv))
    if n_head_kv == n_head:
        return x
    return np.repeat(x, n_head // n_head_kv, axis=1)


@dataclass
class _Layer:
    attn_norm: np.ndarray
    wq: np.ndarray
    wk: np.ndarray
    wv: np.ndarray
    wo: np.ndarray
    ffn_norm: np.ndarray
    w_gate: np.ndarray
    w_up: np.ndarray
    w_down: np.ndarray


class NeoModel:
    """The ``neo`` architecture declared by the GGUF metadata.

    block:  x += attn(rmsnorm(x)) ; x += swiglu(rmsnorm(x))
    attn :  q/k/v projections, rotate-half RoPE, causal softmax, output proj
    ffn  :  silu(x @ gate.T) * (x @ up.T) @ down.T
    head :  rmsnorm, output projection (tied to token_embd when absent)
    """

    def __init__(self, reader: GGUFReader):
        self.reader = reader
        self.cfg = self._config_from_metadata(reader)
        self.eps = self.cfg.norm_eps
        self.layers: List[_Layer] = []
        self._load_weights()
        self.tokenizer = ByteTokenizer(self.cfg.vocab_size)

    # -- config ------------------------------------------------------------ #
    def _config_from_metadata(self, r: GGUFReader) -> NeoConfig:
        md = r.metadata
        arch = md.get("general.architecture")
        if arch != "neo":
            raise NeoShapeError("general.architecture is %r, not 'neo'" % (arch,))
        emb = r.tensors.get("token_embd.weight")
        if emb is None or len(emb.dims) != 2:
            raise NeoShapeError("token_embd.weight missing or not 2-D")
        vocab, dim = emb.shape                       # numpy shape (vocab, dim)
        declared_dim = int(md.get("neo.embedding_length", dim))
        if declared_dim != dim:
            raise NeoShapeError(
                "neo.embedding_length=%d contradicts token_embd.weight shape %r"
                % (declared_dim, emb.shape))
        n_head = int(md.get("neo.attention.head_count", 0))
        if n_head <= 0 or dim % n_head:
            raise NeoShapeError("neo.attention.head_count=%r does not divide dim %d"
                                % (n_head, dim))
        n_head_kv = md.get("neo.attention.head_count_kv", n_head)
        if isinstance(n_head_kv, list):
            n_head_kv = n_head_kv[0] if n_head_kv else n_head
        n_head_kv = int(n_head_kv)
        if n_head_kv <= 0 or n_head % n_head_kv:
            raise NeoShapeError("neo.attention.head_count_kv=%r does not divide %d"
                                % (n_head_kv, n_head))
        ffn = int(md.get("neo.feed_forward_length", 0))
        if ffn <= 0:
            raise NeoShapeError("neo.feed_forward_length missing or invalid")
        n_layer = int(md.get("neo.block_count", 0))
        ctx = int(md.get("neo.context_length", 2048))
        rope = float(md.get("neo.rope.freq_base", 10000.0))
        eps = float(md.get("neo.attention.layer_norm_rms_epsilon", NORM_EPS_DEFAULT))
        return NeoConfig(
            vocab_size=vocab, n_embd=dim, n_layer=n_layer, n_head=n_head,
            n_head_kv=n_head_kv, ffn_length=ffn, context_length=ctx,
            rope_freq_base=rope, norm_eps=eps,
        )

    # -- weights ----------------------------------------------------------- #
    def _get(self, name: str, shape: Sequence[int]) -> np.ndarray:
        arr = self.reader.tensor(name)
        _expect(arr.shape, shape, "weight %s" % name)
        return arr

    def _load_weights(self) -> None:
        c = self.cfg
        r = self.reader
        self.emb = self._get("token_embd.weight", (c.vocab_size, c.n_embd))
        self.out_norm = self._get("output_norm.weight", (c.n_embd,))
        if "output.weight" in r.tensors:
            self.w_out = self._get("output.weight", (c.vocab_size, c.n_embd))
            self.output_tied = False
        else:
            self.w_out = self.emb
            self.output_tied = True
        blocks = {t.name.split(".")[1] for t in r.tensor_list
                  if t.name.startswith("blk.") and t.name.count(".") >= 2}
        if len(blocks) != c.n_layer:
            raise NeoShapeError("block_count=%d but the tensor table has blocks %s"
                                % (c.n_layer, sorted(blocks)))
        for i in range(c.n_layer):
            p = "blk.%d." % i
            kv_dim = c.n_head_kv * c.head_dim
            self.layers.append(_Layer(
                attn_norm=self._get(p + "attn_norm.weight", (c.n_embd,)),
                wq=self._get(p + "attn_q.weight", (c.n_embd, c.n_embd)),
                wk=self._get(p + "attn_k.weight", (kv_dim, c.n_embd)),
                wv=self._get(p + "attn_v.weight", (kv_dim, c.n_embd)),
                wo=self._get(p + "attn_output.weight", (c.n_embd, c.n_embd)),
                ffn_norm=self._get(p + "ffn_norm.weight", (c.n_embd,)),
                w_gate=self._get(p + "ffn_gate.weight", (c.ffn_length, c.n_embd)),
                w_up=self._get(p + "ffn_up.weight", (c.ffn_length, c.n_embd)),
                w_down=self._get(p + "ffn_down.weight", (c.n_embd, c.ffn_length)),
            ))
        self.param_count = sum(a.size for a in self._iter_weights())

    def _iter_weights(self) -> Iterable[np.ndarray]:
        yield self.emb
        yield self.out_norm
        if not self.output_tied:
            yield self.w_out
        for L in self.layers:
            for a in (L.attn_norm, L.wq, L.wk, L.wv, L.wo, L.ffn_norm,
                      L.w_gate, L.w_up, L.w_down):
                yield a

    # -- forward ----------------------------------------------------------- #
    def _rope(self, x: np.ndarray, positions: np.ndarray) -> np.ndarray:
        """Rotate-half RoPE on (T, heads, head_dim). Uses absolute positions."""
        T, nh, hd = x.shape
        half = hd // 2
        if half * 2 != hd:
            raise NeoShapeError("RoPE needs an even head_dim, got %d" % hd)
        inv = (1.0 / (self.cfg.rope_freq_base ** (np.arange(half, dtype=np.float32) * 2.0 / hd))
               ).astype(np.float32)
        theta = positions.astype(np.float32)[:, None] * inv[None, :]      # (T, half)
        cos = np.cos(theta)[:, None, :]
        sin = np.sin(theta)[:, None, :]
        x1 = x[..., :half]
        x2 = x[..., half:]
        out = np.concatenate((x1 * cos - x2 * sin, x2 * cos + x1 * sin), axis=-1)
        _expect(out.shape, (T, nh, hd), "rope output")
        return out.astype(np.float32)

    def forward(self, token_ids: Sequence[int]) -> np.ndarray:
        c = self.cfg
        r = self.reader
        ids = np.asarray(list(token_ids), dtype=np.int64)
        if ids.ndim != 1 or ids.size == 0:
            raise NeoShapeError("forward needs a non-empty 1-D sequence, got %r"
                                % (np.shape(token_ids),))
        if int(ids.min()) < 0 or int(ids.max()) >= c.vocab_size:
            raise NeoShapeError("token ids must be in [0, %d), got [%d, %d]"
                                % (c.vocab_size, int(ids.min()), int(ids.max())))
        T = int(ids.size)
        if T > c.context_length:
            raise NeoShapeError("sequence of %d tokens exceeds context_length %d"
                                % (T, c.context_length))
        D, nh, hd = c.n_embd, c.n_head, c.head_dim
        nkv = c.n_head_kv
        rep = nh // nkv

        x = self.emb[ids]
        _expect(x.shape, (T, D), "embedding")
        _finite("embedding", x)

        positions = np.arange(T, dtype=np.float32)
        mask = np.triu(np.ones((T, T), dtype=bool), k=1)
        scale = np.float32(1.0 / math.sqrt(hd))

        for li, L in enumerate(self.layers):
            h = rms_norm(x, L.attn_norm, self.eps)
            _expect(h.shape, (T, D), "blk.%d attn_norm" % li)
            q = h @ L.wq.T
            k = h @ L.wk.T
            v = h @ L.wv.T
            for nm, arr, width in (("q", q, nh * hd), ("k", k, nkv * hd), ("v", v, nkv * hd)):
                _expect(arr.shape, (T, width), "blk.%d %s projection" % (li, nm))

            q = q.reshape(T, nh, hd)
            k = k.reshape(T, nkv, hd)
            v = v.reshape(T, nkv, hd)
            _expect(q.shape, (T, nh, hd), "blk.%d q heads" % li)
            _expect(k.shape, (T, nkv, hd), "blk.%d k heads" % li)
            q = self._rope(q, positions)
            k = self._rope(k, positions)
            if rep > 1:
                k = expand_kv_heads(k, nh, nkv)
                v = expand_kv_heads(v, nh, nkv)
                _expect(k.shape, (T, nh, hd), "blk.%d k repeat" % li)
                _expect(v.shape, (T, nh, hd), "blk.%d v repeat" % li)

            qh = np.transpose(q, (1, 0, 2))                       # (nh, T, hd)
            kh = np.transpose(k, (1, 0, 2))
            vh = np.transpose(v, (1, 0, 2))
            scores = (qh @ np.transpose(kh, (0, 2, 1))) * scale    # (nh, T, T)
            _expect(scores.shape, (nh, T, T), "blk.%d attention scores" % li)
            scores = np.where(mask[None, :, :], np.float32(-np.inf), scores)
            probs = softmax(scores)
            _finite("blk.%d attention probs" % li, probs)
            ctx = probs @ vh                                     # (nh, T, hd)
            _expect(ctx.shape, (nh, T, hd), "blk.%d attention context" % li)
            ctx = np.transpose(ctx, (1, 0, 2)).reshape(T, D)
            attn = ctx @ L.wo.T
            _expect(attn.shape, (T, D), "blk.%d attn_output" % li)
            x = x + attn

            h2 = rms_norm(x, L.ffn_norm, self.eps)
            gate = h2 @ L.w_gate.T
            up = h2 @ L.w_up.T
            _expect(gate.shape, (T, c.ffn_length), "blk.%d ffn_gate" % li)
            _expect(up.shape, (T, c.ffn_length), "blk.%d ffn_up" % li)
            act = silu(gate) * up
            down = act @ L.w_down.T
            _expect(down.shape, (T, D), "blk.%d ffn_down" % li)
            x = x + down
            _expect(x.shape, (T, D), "blk.%d residual" % li)
            _finite("blk.%d residual" % li, x)

        x = rms_norm(x, self.out_norm, self.eps)
        logits = x @ self.w_out.T
        _expect(logits.shape, (T, c.vocab_size), "logits")
        if not np.isfinite(logits).all():
            raise NeoNumericalError("logits contain %d non-finite values"
                                    % int((~np.isfinite(logits)).sum()))
        return np.ascontiguousarray(logits, dtype=np.float32)

    # -- generation -------------------------------------------------------- #
    def generate(self, prompt_ids: Sequence[int], n_tokens: int = 16,
                 top_k: int = 5) -> Tuple[List[int], List[Dict[str, Any]]]:
        """Greedy decoding, full prefix recompute (no KV cache; O(T^2) by design)."""
        if n_tokens < 1:
            raise ValueError("n_tokens must be >= 1")
        ids = [int(i) for i in prompt_ids]
        if not ids:
            raise NeoShapeError("prompt is empty")
        steps: List[Dict[str, Any]] = []
        for _ in range(n_tokens):
            logits = self.forward(ids)[-1]
            nxt = int(np.argmax(logits))
            order = np.argsort(-logits, kind="stable")[:max(1, top_k)]
            steps.append({
                "position": len(ids),
                "id": nxt,
                "logit": float(logits[nxt]),
                "token": self.tokenizer.token_text(nxt),
                "top_k": [{"id": int(i), "logit": float(logits[i]),
                           "token": self.tokenizer.token_text(int(i))} for i in order],
            })
            ids.append(nxt)
        return ids, steps

    def spec(self) -> Dict[str, Any]:
        return {
            "architecture": "neo",
            "config": self.cfg.as_dict(),
            "params": self.param_count,
            "output_tied": self.output_tied,
            "container": self.reader.header(),
            "torch_free": True,
            "dtype": "float32",
        }


def load_neo(path: str | Path = DEFAULT_GGUF, *, strict: bool = True) -> NeoModel:
    return NeoModel(GGUFReader(path, strict=strict))


def _main(argv: Optional[Sequence[str]] = None) -> int:  # pragma: no cover - CLI shim
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    import neo_infer
    return neo_infer.main(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
