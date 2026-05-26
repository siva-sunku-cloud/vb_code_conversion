"""
Vector DB MCP Server  (Qdrant)

Translation memory: stores previously solved VB → Python patterns so the
Converter Agent can retrieve relevant examples instead of re-deriving them
from scratch on every module.

Requires: qdrant-client  +  a running Qdrant instance (or in-memory mode).
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from config import Config
from utils.logger import get_logger

logger = get_logger("mcp.vectordb")


class VectorDBServer:
    """Thin wrapper around Qdrant for pattern retrieval."""

    COLLECTION = Config.QDRANT_COLLECTION

    def __init__(self, use_memory: bool = False):
        self._available = False
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams, PointStruct

            if use_memory:
                self._client = QdrantClient(":memory:")
            else:
                self._client = QdrantClient(
                    url=Config.QDRANT_URL,
                    api_key=Config.QDRANT_API_KEY or None,
                )

            self._PointStruct = PointStruct
            self._Distance = Distance
            self._VectorParams = VectorParams
            self._ensure_collection()
            self._available = True
            logger.info("VectorDB connected")
        except Exception as exc:
            logger.warning(f"VectorDB unavailable — translation memory disabled. ({exc})")

    # ── Public API ────────────────────────────────────────────────────────────

    def store_pattern(self, vb_snippet: str, python_snippet: str, description: str) -> None:
        if not self._available:
            return
        vec = self._embed(vb_snippet)
        point = self._PointStruct(
            id=int(hashlib.md5(vb_snippet.encode()).hexdigest(), 16) % (2**63),
            vector=vec,
            payload={
                "vb_snippet": vb_snippet,
                "python_snippet": python_snippet,
                "description": description,
            },
        )
        self._client.upsert(collection_name=self.COLLECTION, points=[point])

    def search_patterns(self, vb_snippet: str, top_k: int = 3) -> list[dict]:
        if not self._available:
            return []
        vec = self._embed(vb_snippet)
        hits = self._client.search(
            collection_name=self.COLLECTION,
            query_vector=vec,
            limit=top_k,
        )
        return [h.payload for h in hits]

    # ── Private ───────────────────────────────────────────────────────────────

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if self.COLLECTION not in existing:
            self._client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=self._VectorParams(size=128, distance=self._Distance.COSINE),
            )

    def _embed(self, text: str) -> list[float]:
        # Deterministic 128-dim hash embedding — replace with a real embedding
        # model (e.g. anthropic.embeddings or sentence-transformers) in production.
        digest = hashlib.sha512(text.encode()).digest()
        return [(b - 128) / 128.0 for b in digest]
