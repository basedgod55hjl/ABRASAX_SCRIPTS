#!/usr/bin/env python3
"""CLI for the ABRASAX-NEO GGUF checkpoint.

    python SCRIPTS/tools/neo_infer.py --info
    python SCRIPTS/tools/neo_infer.py --prompt "hello world" --tokens 16
    python SCRIPTS/tools/neo_infer.py --prompt "hello world" --tokens 16 --json

Prints the parsed metadata, the tensor table with absolute byte ranges, then a
greedy continuation with token ids and decoded text. Exit codes: 0 success,
2 container/model error (bad magic, corrupt offset, missing file, ...).

There is no logit smoothing, no temperature, no sampling: greedy ``argmax`` over
the model's own float32 logits. The weights are deterministic K/PHI streams, so
the text is token soup by construction -- the numbers are real.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from neo_loader import (  # noqa: E402
    DEFAULT_GGUF,
    ByteTokenizer,
    GGUFError,
    GGUFReader,
    NeoModel,
)


def _safe(text: str) -> str:
    enc = sys.stdout.encoding or "utf-8"
    return text.encode(enc, "backslashreplace").decode(enc)


def _fmt_value(value: Any, limit: int = 96) -> str:
    if isinstance(value, str):
        s = repr(value)
    elif isinstance(value, float):
        s = repr(value)
    elif isinstance(value, list):
        s = "[" + ", ".join(_fmt_value(v, limit) for v in value[:8])
        s += ", ...]" if len(value) > 8 else "]"
    else:
        s = str(value)
    return s if len(s) <= limit else s[: limit - 3] + "..."


def _print_metadata(reader: GGUFReader) -> None:
    print("metadata (%d keys)" % len(reader.metadata))
    print("  %-36s %-9s %s" % ("key", "type", "value"))
    for key, value in reader.metadata.items():
        print("  %-36s %-9s %s" % (key, reader.kv_types.get(key, "?"), _fmt_value(value)))


def _print_tensor_table(reader: GGUFReader) -> None:
    print()
    print("tensors (%d, %d params, %d bytes payload)"
          % (len(reader.tensor_list), reader.param_count, reader.tensor_bytes))
    print(reader.tensor_table())


def _run(args: argparse.Namespace):
    reader = GGUFReader(args.model, strict=not args.lax)
    result: Dict[str, Any] = {
        "ok": True,
        "model": str(Path(args.model)),
        "container": reader.header(),
        "sha256": hashlib.sha256(reader._data).hexdigest(),
        "metadata": reader.metadata,
        "metadata_types": reader.kv_types,
        "param_count": reader.param_count,
        "tensor_bytes": reader.tensor_bytes,
        "type_histogram": reader._type_histogram(),
        "tensors": [t.as_dict(reader.tensor_data_offset) for t in reader.tensor_list],
    }
    if args.info:
        return result, reader, None

    model = NeoModel(reader)
    tok: ByteTokenizer = model.tokenizer
    prompt_ids = tok.encode(args.prompt)
    if not prompt_ids:
        raise GGUFError("prompt encodes to zero tokens")
    if len(prompt_ids) > args.max_prompt_tokens:
        raise GGUFError("prompt encodes to %d tokens, above --max-prompt-tokens %d"
                        % (len(prompt_ids), args.max_prompt_tokens))
    logits = model.forward(prompt_ids)
    all_ids, steps = model.generate(prompt_ids, args.tokens, top_k=args.top_k)
    gen_ids = all_ids[len(prompt_ids):]
    last = logits[-1]
    order = np.argsort(-last, kind="stable")[: args.top_k]
    top = [{"id": int(i), "logit": float(last[i]), "token": tok.token_text(int(i))}
           for i in order]
    decoded = tok.decode(gen_ids)
    result.update({
        "prompt": args.prompt,
        "prompt_ids": prompt_ids,
        "logits_shape": list(logits.shape),
        "logits_sha256": hashlib.sha256(logits.tobytes()).hexdigest(),
        "logits_min": float(logits.min()),
        "logits_max": float(logits.max()),
        "logits_finite": bool(np.isfinite(logits).all()),
        "top_k_last": top,
        "generated_ids": gen_ids,
        "generated_text": decoded,
        "generated_hex": bytes((i % 256) for i in gen_ids).hex(),
        "steps": steps,
        "config": model.cfg.as_dict(),
        "params": model.param_count,
        "output_tied": model.output_tied,
    })
    return result, reader, model


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="neo_infer",
        description="Parse ABRASAX-NEO.gguf and run a greedy float32 forward pass.")
    ap.add_argument("--model", default=str(DEFAULT_GGUF),
                    help="path to the .gguf (default: %(default)s)")
    ap.add_argument("--prompt", default="hello world", help="prompt text (UTF-8 bytes)")
    ap.add_argument("--tokens", type=int, default=16, help="tokens to generate (default 16)")
    ap.add_argument("--top-k", type=int, default=5, help="top-k logits to report")
    ap.add_argument("--max-prompt-tokens", type=int, default=256)
    ap.add_argument("--json", action="store_true", help="machine-readable output only")
    ap.add_argument("--info", action="store_true", help="container/tensor table, no inference")
    ap.add_argument("--lax", action="store_true",
                    help="downgrade gap/trailing-byte strictness (offsets are still bounds-checked)")
    args = ap.parse_args(argv)
    if args.tokens < 1:
        ap.error("--tokens must be >= 1")

    try:
        result, reader, _model = _run(args)
    except (GGUFError, FileNotFoundError, ValueError) as exc:
        payload = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
        sys.stderr.write(json.dumps(payload) + "\n")
        return 2

    if args.json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=True)
        sys.stdout.write("\n")
        return 0

    print("ABRASAX-NEO loader  (GGUF v3 reader + float32 forward, no torch)")
    print("file      : %s (%d bytes)" % (result["model"], result["container"]["file_bytes"]))
    print("sha256    : %s" % result["sha256"])
    print("header    : magic=%s version=%d tensors=%d kv=%d" % (
        result["container"]["magic"], result["container"]["version"],
        result["container"]["tensor_count"], result["container"]["kv_count"]))
    print("alignment : %d  tensor_data_offset=%d  payload=%d  trailing=%d  gaps=%s" % (
        result["container"]["alignment"], result["container"]["tensor_data_offset"],
        result["container"]["tensor_data_size"], result["container"]["trailing_bytes"],
        result["container"]["gaps"] or "[]"))
    print("params    : %d  types=%s" % (result["param_count"], result["type_histogram"]))
    print()
    _print_metadata(reader)
    _print_tensor_table(reader)
    if args.info:
        return 0

    print()
    print("inference (greedy argmax, float32, full-prefix recompute)")
    print("config    : %s" % json.dumps(result["config"]))
    print("prompt    : %r -> %d tokens %s" % (args.prompt, len(result["prompt_ids"]),
                                              result["prompt_ids"]))
    print("logits    : shape=%s finite=%s min=%.4f max=%.4f sha256=%s" % (
        tuple(result["logits_shape"]), result["logits_finite"],
        result["logits_min"], result["logits_max"], result["logits_sha256"]))
    print("top-%d     : %s" % (args.top_k, ", ".join(
        "%d(%s)=%.6f" % (t["id"], t["token"], t["logit"]) for t in result["top_k_last"])))
    print("generated : %d tokens %s" % (len(result["generated_ids"]), result["generated_ids"]))
    print("text      : %s" % _safe(repr(result["generated_text"])))
    print("hex       : %s" % result["generated_hex"])
    print("steps     :")
    for st in result["steps"]:
        print("  pos %2d -> id %3d %-14s logit %+.6f" % (
            st["position"], st["id"], st["token"], st["logit"]))
    print()
    print("note      : the checkpoint has no tokenizer (byte vocabulary) and its weights "
          "are deterministic K/PHI streams; token soup is the expected output.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
