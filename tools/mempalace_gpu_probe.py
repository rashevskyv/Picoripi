"""Verify the optional MemPalace CUDA environment and print machine-readable data."""

from __future__ import annotations

import argparse
import json
import time


def probe(matrix_size: int = 2048, repeats: int = 5) -> dict:
    try:
        import torch
    except ImportError:
        return {
            "available": False,
            "reason": "PyTorch is not installed in this Python environment.",
        }

    if not torch.cuda.is_available():
        return {
            "available": False,
            "torch_version": torch.__version__,
            "reason": "PyTorch could not initialize CUDA.",
        }

    device = torch.device("cuda")
    left = torch.randn((matrix_size, matrix_size), device=device, dtype=torch.float16)
    right = torch.randn((matrix_size, 512), device=device, dtype=torch.float16)
    _ = left @ right
    torch.cuda.synchronize()
    started = time.perf_counter()
    for _ in range(repeats):
        result = left @ right
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    return {
        "available": True,
        "torch_version": torch.__version__,
        "device": torch.cuda.get_device_name(0),
        "compute_capability": list(torch.cuda.get_device_capability(0)),
        "benchmark_seconds": round(elapsed, 6),
        "repeats": repeats,
        "matrix_size": matrix_size,
        "peak_memory_mb": round(torch.cuda.max_memory_allocated() / 1024 / 1024, 1),
        "checksum": round(float(result[0, 0]), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-size", type=int, default=2048)
    parser.add_argument("--repeats", type=int, default=5)
    arguments = parser.parse_args()
    report = probe(arguments.matrix_size, arguments.repeats)
    print(json.dumps(report, indent=2))
    return 0 if report["available"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
