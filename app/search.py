"""
Discovery: capability-based search rather than exact keyword match.

Real systems would embed `name + description + capabilities` with a sentence-embedding model and
do ANN lookup. To keep this sample dependency-free and instant to run, we approximate "semantic-ish"
matching with: (1) a small hand-rolled TF-IDF cosine score over free text, (2) a boost when the
query overlaps an agent's declared `capabilities`/`tags` (structured signal beats free text), and
(3) a light synonym table so "reconcile invoices" also matches "billing reconciliation". It's not a
real embedding model — but it demonstrates the point that discovery should rank by *what an agent
can do*, not by whether the query string happens to appear in its name.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.models import AgentManifest

SYNONYMS: dict[str, list[str]] = {
    "reconcile": ["reconciliation", "reconciling", "billing", "invoice", "invoices"],
    "invoice": ["billing", "invoices", "reconcile"],
    "triage": ["route", "routing", "classify", "classification"],
    "support": ["ticket", "tickets", "helpdesk", "customer"],
    "anomaly": ["anomalies", "outlier", "fraud", "flag"],
    "code": ["pr", "pull request", "review", "diff"],
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    expanded = list(tokens)
    for t in tokens:
        expanded.extend(SYNONYMS.get(t, []))
    return expanded


def _agent_document(m: AgentManifest) -> str:
    return " ".join([m.name, m.description, " ".join(m.capabilities), " ".join(m.tags)])


@dataclass
class SearchHit:
    manifest: AgentManifest
    score: float
    matched_capabilities: list[str]


def score_agents(query: str, agents: list[AgentManifest]) -> list[SearchHit]:
    if not query.strip():
        # No query: stable order, most-trusted-ish first (approved, verified) then name.
        ranked = sorted(
            agents,
            key=lambda m: (m.review.status.value != "approved", not m.publisher.verified, m.name),
        )
        return [SearchHit(m, 1.0, []) for m in ranked]

    query_tokens = Counter(_tokenize(query))

    # document frequency across the corpus, for IDF
    docs_tokens = [Counter(_tokenize(_agent_document(m))) for m in agents]
    df: Counter[str] = Counter()
    for doc in docs_tokens:
        for term in doc:
            df[term] += 1
    n_docs = max(len(agents), 1)

    hits: list[SearchHit] = []
    for manifest, doc_tokens in zip(agents, docs_tokens):
        score = 0.0
        for term, q_count in query_tokens.items():
            if term not in doc_tokens:
                continue
            tf = doc_tokens[term] / max(sum(doc_tokens.values()), 1)
            idf = math.log((n_docs + 1) / (df[term] + 1)) + 1.0
            score += tf * idf * q_count

        query_terms = set(query_tokens)
        capability_terms = set(_tokenize(" ".join(manifest.capabilities)))
        matched_caps = sorted(
            cap for cap in manifest.capabilities
            if query_terms & set(_tokenize(cap))
        )
        if matched_caps:
            score += 0.5 * len(matched_caps)  # structured signal beats free-text overlap

        if score > 0:
            hits.append(SearchHit(manifest, round(score, 4), matched_caps))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits
