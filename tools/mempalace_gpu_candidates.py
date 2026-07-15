"""CUDA semantic candidate retrieval for the MemPalace alignment engine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time


def _segments(text: str, size: int = 80, stride: int = 60) -> list[str]:
    words = str(text or "").split()
    if not words:
        return [""]
    return [
        " ".join(words[start:start + size])
        for start in range(0, len(words), stride)
        if words[start:start + size]
    ]


def retrieve(payload: dict, model_name: str, top_k: int) -> dict:
    import torch
    from sentence_transformers import SentenceTransformer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available in the GPU Python environment.")
    started = time.perf_counter()
    model = SentenceTransformer(model_name, device="cuda")
    segment_texts = []
    segment_nodes = []
    for dialogue in payload["dialogues"]:
        for segment in _segments(dialogue["text"]):
            segment_texts.append(segment)
            segment_nodes.append(int(dialogue["node_id"]))
    message_texts = [message["text"] for message in payload["messages"]]
    message_embeddings = model.encode(
        message_texts,
        batch_size=256,
        convert_to_tensor=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    candidates: dict[int, dict[int, float]] = {}
    batch_size = 1024
    actual_top_k = min(top_k, len(message_texts))
    for start in range(0, len(segment_texts), batch_size):
        batch_texts = segment_texts[start:start + batch_size]
        embeddings = model.encode(
            batch_texts,
            batch_size=256,
            convert_to_tensor=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        scores, indices = torch.topk(
            embeddings @ message_embeddings.T,
            k=actual_top_k,
            dim=1,
        )
        for offset, node_id in enumerate(segment_nodes[start:start + batch_size]):
            node_candidates = candidates.setdefault(node_id, {})
            for message_index, score in zip(
                indices[offset].tolist(), scores[offset].tolist(), strict=True
            ):
                node_candidates[message_index] = max(
                    score, node_candidates.get(message_index, -1.0)
                )
    return {
        "backend": "cuda_embeddings",
        "device": torch.cuda.get_device_name(0),
        "model": model_name,
        "segments": len(segment_texts),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "candidates": {
            str(node_id): sorted(
                ((index, round(score, 6)) for index, score in values.items()),
                key=lambda item: item[1],
                reverse=True,
            )
            for node_id, values in candidates.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--top-k", type=int, default=16)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = retrieve(payload, args.model, args.top_k)
    args.output.write_text(json.dumps(report), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "candidates"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
