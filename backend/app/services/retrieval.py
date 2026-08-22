from typing import Any

import numpy as np

from app.db import Event
from app.services.embeddings import EmbeddingService


def _content_for_event(event: Event) -> str:
    parts = [event.role or "", event.content or "", event.reasoning or ""]
    if event.tool_calls:
        parts.append(str(event.tool_calls))
    if event.browser_action:
        parts.append(str(event.browser_action))
    return "\n".join(parts)


class ContextRetriever:
    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding = embedding_service or EmbeddingService()

    def build_context(
        self,
        events: list[Event],
        query: str,
        max_tokens: int = 8000,
        token_per_char: int = 4,
    ) -> list[dict[str, Any]]:
        if not events:
            return []

        # Always include the most recent 10 turns fully.
        recent = events[-10:]
        recent_ids = {e.id for e in recent}

        # Retrieve older semantically relevant events.
        older = [e for e in events if e.id not in recent_ids and e.embedding]
        selected = recent[:]

        if older and query:
            q_emb = np.array(self.embedding.encode([query])[0])
            scored = []
            for e in older:
                e_emb = np.array(e.embedding)
                a = q_emb / (np.linalg.norm(q_emb) + 1e-10)
                b = e_emb / (np.linalg.norm(e_emb) + 1e-10)
                score = float(np.dot(a, b))
                scored.append((score, e))
            scored.sort(key=lambda x: x[0], reverse=True)

            budget_used = sum(len(_content_for_event(e)) // token_per_char for e in recent)
            for score, e in scored:
                cost = len(_content_for_event(e)) // token_per_char
                if budget_used + cost > max_tokens:
                    break
                if e not in selected:
                    selected.append(e)
                    budget_used += cost

        selected.sort(key=lambda e: e.id)

        context = []
        for e in selected:
            entry: dict[str, Any] = {"role": e.role}
            if e.content:
                entry["content"] = e.content
            if e.reasoning:
                entry["reasoning"] = e.reasoning
            if e.tool_calls:
                entry["tool_calls"] = e.tool_calls
            if e.browser_action:
                entry["browser_action"] = e.browser_action
            context.append(entry)
        return context
