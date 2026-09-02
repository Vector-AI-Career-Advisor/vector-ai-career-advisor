from __future__ import annotations
import logging
from typing import Dict, List, Optional
import chromadb
from chromadb.config import Settings
from server.web.core.config import CHROMA_PERSIST_DIR, CHROMA_COLLECTION
from .embeddings import get_embeddings
from server.etl.utils import build_chroma_metadata

log = logging.getLogger(__name__)

# Fields that get their own dedicated embedding vector in addition to the full-text vector
FIELD_VECTORS = [
    "skills_must",
    "skills_nice",
    "description",
    "title",
    "role",
    "company",
    "location",
]

# Maximum vectors per ChromaDB upsert call — keeps memory bounded on large runs
_UPSERT_BATCH_SIZE = 500


# ── Init ──────────────────────────────────────────────────────────────────────

def init_chroma() -> chromadb.Collection:
    client = chromadb.PersistentClient(
        path=CHROMA_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    log.info("ChromaDB collection '%s' | %d vectors.", CHROMA_COLLECTION, collection.count())
    return collection


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_full_text(job: dict) -> str:
    """Combine all job fields into a single string for the full-text vector."""
    def _join(val):
        return ", ".join(str(v) for v in val if v) if isinstance(val, list) else str(val or "")

    return f"""
Job Title: {job.get('title', '')}
Role: {job.get('role', '')}
Seniority: {job.get('seniority', '')}
Company: {job.get('company', '')}
Location: {_join([job.get('location'), job.get('region')])}

Required Skills: {_join(job.get('skills_must', []))}
Nice Skills: {_join(job.get('skills_nice', []))}
Experience: {job.get('yearsexperience', '')} years
Past Experience: {_join(job.get('past_experience', []))}
Education: {_join(job.get('education', []))}

Description:
{job.get('description', '')}
""".strip()


def _field_text(job: dict, field: str) -> str:
    """Return a clean string for a single job field."""
    if field == "location":
        parts = [job.get("location"), job.get("region")]
        return ", ".join(str(p).strip() for p in parts if p)
    val = job.get(field, "")
    if isinstance(val, list):
        return ", ".join(str(v) for v in val if v)
    return str(val).strip() if val else ""


def _chroma_upsert_batch(
    collection: chromadb.Collection,
    ids: List[str],
    documents: List[str],
    embeddings: List[List[float]],
    metadatas: List[dict],
) -> None:
    """Upsert in chunks to stay within ChromaDB's recommended batch size."""
    for start in range(0, len(ids), _UPSERT_BATCH_SIZE):
        end = start + _UPSERT_BATCH_SIZE
        collection.upsert(
            ids=ids[start:end],
            documents=documents[start:end],
            embeddings=embeddings[start:end],
            metadatas=metadatas[start:end],
        )


# ── Writes ────────────────────────────────────────────────────────────────────

def upsert_jobs(collection: chromadb.Collection, jobs: List[dict]) -> int:
    """
    Upsert jobs into ChromaDB.

    Each job produces:
      - 1 full-text vector
      - 1 vector per FIELD_VECTORS field (if the field has content)

    All texts across ALL jobs are embedded in a single batch call,
    then upserted to ChromaDB in one chunked call — minimising both
    embedding latency and ChromaDB round-trips.

    Returns total number of vectors upserted.
    """
    if not jobs:
        return 0

    # ── Build all texts and record structure ──────────────────────────────────
    # plan: list of (vector_id, text, metadata) tuples, in order
    plan: list[tuple[str, str, dict]] = []

    for job in jobs:
        job_id = job["id"]
        meta   = build_chroma_metadata(job)

        # Full-text vector
        full_text = _build_full_text(job)
        plan.append((f"{job_id}_full", full_text, {"job_id": job_id, "type": "full", **meta}))

        # Per-field vectors (only for non-empty fields)
        for field in FIELD_VECTORS:
            text = _field_text(job, field)
            if text:
                plan.append((
                    f"{job_id}_{field}",
                    text,
                    {"job_id": job_id, "type": "field", "field": field, **meta},
                ))

    # ── Single batch embedding call for ALL texts ─────────────────────────────
    all_texts = [text for _, text, _ in plan]
    log.info("Embedding %d texts for %d jobs in one batch call...", len(all_texts), len(jobs))
    all_vecs = get_embeddings(all_texts)

    # ── Single batched upsert ─────────────────────────────────────────────────
    ids       = [vec_id  for vec_id, _, _  in plan]
    documents = [text    for _, text, _    in plan]
    metadatas = [meta    for _, _, meta    in plan]

    _chroma_upsert_batch(collection, ids, documents, all_vecs, metadatas)

    total = len(plan)
    log.info("Upserted %d vectors for %d jobs.", total, len(jobs))
    return total


# ── Reads ─────────────────────────────────────────────────────────────────────

def search_jobs(
    collection: chromadb.Collection,
    query: str,
    n_results: int = 10,
    where: Optional[Dict] = None,
) -> List[Dict]:
    """Semantic search. Returns hits sorted by score descending."""
    query_embedding = get_embeddings(query.strip() or " ")[0]

    kwargs = dict(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    hits = [
        {
            "id":       doc_id,
            "score":    1 - results["distances"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
        }
        for i, doc_id in enumerate(results["ids"][0])
    ]
    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits


def get_existing_ids(collection: chromadb.Collection) -> set:
    return set(collection.get(include=[])["ids"])


def collection_count(collection: chromadb.Collection) -> int:
    return collection.count()