from typing import Any

import numpy as np


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a / (np.linalg.norm(a) + 1e-10)
    b = b / (np.linalg.norm(b) + 1e-10)
    return float(np.dot(a, b))


class EmbeddingService:
    def __init__(self, settings: Any | None = None) -> None:
        from app.settings import get_settings

        self.settings = settings or get_settings()
        self._model = None
        self._fallback = False

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                self.settings.embedding_model,
                device=self.settings.embedding_device,
            )
        except (ImportError, RuntimeError, OSError):
            # Fallback when sentence-transformers/torch is not installed.
            self._fallback = True
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load_model()
        if model:
            embeddings = model.encode(texts, convert_to_numpy=True)
            return [e.tolist() for e in embeddings]

        # Deterministic fallback using simple character hashing + random projection.
        import hashlib

        result = []
        for text in texts:
            h = hashlib.sha256(text.encode()).digest()
            vec = [((h[i % len(h)] - 128) / 128.0) for i in range(self.settings.pgvector_dim)]
            result.append(vec)
        return result
