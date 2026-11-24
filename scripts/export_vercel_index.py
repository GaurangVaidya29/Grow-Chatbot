"""Export the active Chroma collection as a compact read-only Vercel asset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import PROJECT_ROOT, load_config
from app.scraper import load_source_registry
from app.vector_store import ChromaVectorStore


OUTPUT_PATH = PROJECT_ROOT / "data" / "vercel" / "index.json"


def main() -> int:
    config = load_config()
    store = ChromaVectorStore(config.vector_db)
    manifest = store.validate_compatibility(
        embedding_model=config.embeddings.model,
        normalized_embeddings=config.embeddings.normalize,
    )
    collection = store.client.get_collection(name=manifest.active_collection)
    result = collection.get(include=["documents", "metadatas", "embeddings"])
    sources = {source.source_id: source for source in load_source_registry() if source.enabled}

    records = []
    for chunk_id, text, metadata, embedding in zip(
        result["ids"],
        result["documents"],
        result["metadatas"],
        result["embeddings"],
        strict=True,
    ):
        records.append(
            {
                "chunk_id": chunk_id,
                "text": text,
                "embedding": [round(float(value), 8) for value in embedding],
                "source_id": metadata["source_id"],
                "scheme_id": metadata.get("scheme_id") or None,
                "fact_type": metadata["fact_type"],
                "retrieved_at": metadata["retrieved_at"],
            }
        )

    payload = {
        "embedding_model": manifest.embedding_model,
        "embedding_dimension": manifest.embedding_dimension,
        "normalized_embeddings": manifest.normalized_embeddings,
        "index_version": manifest.index_version,
        "score_threshold": config.retrieval.score_threshold,
        "top_k": config.retrieval.top_k,
        "sources": {
            source_id: {
                "source_id": source.source_id,
                "title": source.title,
                "scheme_id": source.scheme_id,
                "url": str(source.url),
            }
            for source_id, source in sorted(sources.items())
        },
        "records": sorted(records, key=lambda item: item["chunk_id"]),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"Exported {len(records)} records ({manifest.embedding_dimension} dimensions) "
        f"to {OUTPUT_PATH.relative_to(PROJECT_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
