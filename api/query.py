"""Vercel serverless adapter for the grounded FAQ query pipeline."""

from __future__ import annotations

import json
import math
import os
import re
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from groq import Groq
from huggingface_hub import InferenceClient


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "data" / "vercel" / "index.json"
MAX_QUESTION_CHARACTERS = 1_000

SCHEME_ALIASES = {
    "hdfc_mutual_fund": ("hdfc mutual fund", "hdfc amc"),
    "hdfc_large_cap_direct_growth": (
        "hdfc large cap fund direct growth",
        "hdfc large cap direct growth",
        "hdfc large cap fund",
        "hdfc large cap",
    ),
    "hdfc_flexi_cap_direct_growth": (
        "hdfc flexi cap direct plan growth",
        "hdfc flexi cap direct growth",
        "hdfc flexi cap fund",
        "hdfc flexi cap",
        "hdfc equity fund direct growth",
    ),
    "hdfc_elss_direct_growth": (
        "hdfc elss tax saver fund direct plan growth",
        "hdfc elss tax saver fund",
        "hdfc elss fund",
        "hdfc elss",
        "hdfc tax saver fund",
    ),
    "hdfc_mid_cap_direct_growth": (
        "hdfc mid cap fund direct growth",
        "hdfc mid cap direct growth",
        "hdfc mid cap fund",
        "hdfc mid cap",
    ),
}

FACT_PATTERNS = (
    ("expense_ratio", re.compile(r"\b(?:expense ratio|ter)\b", re.I)),
    ("exit_load", re.compile(r"\b(?:exit load|redemption (?:fee|charge))\b", re.I)),
    ("minimum_sip", re.compile(r"\b(?:minimum|min)\s+sip\b|\bsip\s+(?:minimum|amount)\b", re.I)),
    ("lock_in", re.compile(r"\b(?:lock[ -]?in|tax saver lock)\b", re.I)),
    ("riskometer", re.compile(r"\b(?:riskometer|risk level|how risky|risk rating)\b", re.I)),
    ("benchmark", re.compile(r"\b(?:benchmark|benchmarked|index tracked)\b", re.I)),
    ("statement_process", re.compile(r"\b(?:capital gains? statement|download statement|account statement)\b", re.I)),
)
SCHEME_REQUIRED_FACTS = {
    "expense_ratio",
    "exit_load",
    "minimum_sip",
    "lock_in",
    "riskometer",
    "benchmark",
}

PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.I)
AADHAAR_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){11}\d(?!\d)")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?91[ -]?)?[6-9]\d{9}(?!\d)")
OTP_PATTERN = re.compile(r"\b(?:otp|one[ -]?time password|passcode)\b.{0,30}\b\d{4,8}\b", re.I)
ACCOUNT_PATTERN = re.compile(
    r"\b(?:account|a/c|folio)\s*(?:number|no\.?|#)?\s*(?:is\s*)?[:=-]?\s*\d{8,18}\b",
    re.I,
)
ADVICE_PATTERNS = (
    re.compile(r"\bshould\s+i\b", re.I),
    re.compile(r"\b(?:buy|sell|hold|switch)\b", re.I),
    re.compile(r"\b(?:best|recommend|recommendation|suitable|suitability)\b", re.I),
    re.compile(r"\bportfolio\b", re.I),
)
PERFORMANCE_PATTERNS = (
    re.compile(r"\b(?:returns?|cagr|performance|alpha)\b", re.I),
    re.compile(r"\b(?:project|projection|forecast|future value)\b", re.I),
)
OUT_OF_SCOPE_PATTERNS = (
    re.compile(r"\b(?:weather|recipe|movie|sports?|cricket)\b", re.I),
    re.compile(r"\b(?:stock|share|crypto|bitcoin|loan|insurance)\b", re.I),
)
SENSITIVE_PATTERNS = (
    PAN_PATTERN,
    AADHAAR_PATTERN,
    EMAIL_PATTERN,
    PHONE_PATTERN,
    OTP_PATTERN,
    ACCOUNT_PATTERN,
)

TEMPLATES = {
    "ADVICE_OR_OPINION": "I can provide verified fund facts, but I cannot recommend whether to buy, sell, hold, or switch an investment.",
    "PERFORMANCE_REQUEST": "I cannot calculate, compare, rank, or project investment performance. I can help with verified scheme facts instead.",
    "OUT_OF_SCOPE": "That question is outside this facts-only HDFC mutual fund FAQ.",
    "SENSITIVE_DATA": "Please do not share personal or financial identifiers here. Remove the sensitive information and ask a general fund question.",
    "UNSUPPORTED_BY_SOURCES": "I could not verify that fact from the approved source pages, so I will not guess.",
    "CLARIFICATION_REQUIRED": "Please specify one scheme: HDFC Large Cap, Flexi Cap, ELSS Tax Saver, or Mid Cap.",
    "SERVICE_ERROR": "The verified source service is temporarily unavailable. Please try again later.",
}

_INDEX: dict[str, Any] | None = None


def load_index() -> dict[str, Any]:
    global _INDEX
    if _INDEX is None:
        _INDEX = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return _INDEX


def resolve_scheme(question: str) -> tuple[str | None, tuple[str, ...]]:
    normalized = " ".join(question.lower().split())
    matches = {
        scheme_id
        for scheme_id, aliases in SCHEME_ALIASES.items()
        if any(re.search(rf"\b{re.escape(alias)}\b", normalized) for alias in aliases)
    }
    candidates = tuple(sorted(matches))
    return (candidates[0] if len(candidates) == 1 else None, candidates)


def resolve_fact_type(question: str) -> str:
    for fact_type, pattern in FACT_PATTERNS:
        if pattern.search(question):
            return fact_type
    return "general"


def classify(question: str) -> str:
    if any(pattern.search(question) for pattern in SENSITIVE_PATTERNS):
        return "SENSITIVE_DATA"
    if any(pattern.search(question) for pattern in ADVICE_PATTERNS):
        return "ADVICE_OR_OPINION"
    if any(pattern.search(question) for pattern in PERFORMANCE_PATTERNS):
        return "PERFORMANCE_REQUEST"
    if any(pattern.search(question) for pattern in OUT_OF_SCOPE_PATTERNS):
        return "OUT_OF_SCOPE"
    return "FACTUAL_CANDIDATE"


def source_for(index: dict[str, Any], *, scheme_id: str | None = None, source_id: str | None = None) -> dict[str, Any]:
    sources = index["sources"]
    if source_id and source_id in sources:
        return sources[source_id]
    if scheme_id:
        for source in sources.values():
            if source.get("scheme_id") == scheme_id:
                return source
    return sources["SRC-01"]


def response_payload(
    index: dict[str, Any],
    category: str,
    answer: str,
    *,
    scheme_id: str | None = None,
    source_id: str | None = None,
    evidence_ids: list[str] | None = None,
    source_updated_at: str | None = None,
) -> dict[str, Any]:
    source = source_for(index, scheme_id=scheme_id, source_id=source_id)
    if source_updated_at is None:
        dates = [
            record["retrieved_at"]
            for record in index["records"]
            if record["source_id"] == source["source_id"]
        ]
        source_updated_at = max(dates)
    return {
        "category": category,
        "answer": answer,
        "citation": {
            "source_id": source["source_id"],
            "label": source["title"],
            "url": source["url"],
        },
        "source_updated_at": source_updated_at,
        "evidence_chunk_ids": evidence_ids or [],
    }


def query_embedding(question: str, index: dict[str, Any]) -> list[float]:
    token = os.environ.get("HF_TOKEN", "").strip()
    configured_model = os.environ.get("HF_EMBEDDING_MODEL", index["embedding_model"]).strip()
    if not token:
        raise RuntimeError("HF_TOKEN is not configured")
    if configured_model != index["embedding_model"]:
        raise RuntimeError("Embedding model does not match the exported index")
    client = InferenceClient(provider="hf-inference", api_key=token)
    result = client.feature_extraction(
        question,
        model=configured_model,
        normalize=True,
    )
    vector = result.tolist() if hasattr(result, "tolist") else list(result)
    if vector and isinstance(vector[0], list):
        vector = vector[0]
    if len(vector) != index["embedding_dimension"]:
        raise RuntimeError("Query embedding dimension does not match the index")
    return [float(value) for value in vector]


def retrieve(question: str, index: dict[str, Any], scheme_id: str | None, fact_type: str) -> list[dict[str, Any]]:
    vector = query_embedding(question, index)
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise RuntimeError("Query embedding has zero magnitude")
    vector = [value / norm for value in vector]
    candidates = []
    for record in index["records"]:
        if scheme_id and record.get("scheme_id") != scheme_id:
            continue
        if fact_type != "general" and record.get("fact_type") != fact_type:
            continue
        score = sum(a * b for a, b in zip(vector, record["embedding"], strict=True))
        if score >= index["score_threshold"]:
            candidates.append({**record, "score": score})
    return sorted(candidates, key=lambda item: item["score"], reverse=True)[: index["top_k"]]


def numbers(text: str) -> set[str]:
    return set(re.findall(r"(?<!\w)\d+(?:[.,]\d+)*(?:%|\s*years?)?", text, re.I))


def sentence_count(text: str) -> int:
    return len([part for part in re.split(r"(?<=[.!?])(?:\s+|$)", text.strip()) if part])


def generate(question: str, scheme_id: str | None, fact_type: str, hits: list[dict[str, Any]], index: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get("LLM_PROVIDER", "groq").lower() != "groq":
        raise RuntimeError("Only Groq is supported")
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("LLM_MODEL", "qwen/qwen3.8-27b").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    evidence = [
        {
            "chunk_id": hit["chunk_id"],
            "source_id": hit["source_id"],
            "text": hit["text"],
        }
        for hit in hits
    ]
    prompt = (
        "Answer only from the supplied evidence. Do not add advice, performance comparisons, "
        "sensitive data, or URLs. Use no more than three sentences. Return JSON with exactly "
        "category, answer_text, selected_source_id, evidence_chunk_ids. category must be "
        "FACTUAL_SUPPORTED. Select only supplied source and chunk IDs.\n"
        f"Question: {question}\nCanonical scheme: {scheme_id}\nFact type: {fact_type}\n"
        f"Evidence: {json.dumps(evidence, ensure_ascii=False)}"
    )
    completion = Groq(api_key=api_key).chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a facts-only mutual fund FAQ answerer."},
            {"role": "user", "content": prompt},
        ],
    )
    content = completion.choices[0].message.content
    if not content:
        raise RuntimeError("Groq returned an empty response")
    generated = json.loads(content)
    hit_by_id = {hit["chunk_id"]: hit for hit in hits}
    evidence_ids = generated.get("evidence_chunk_ids")
    source_id = generated.get("selected_source_id")
    answer = str(generated.get("answer_text", "")).strip()
    if generated.get("category") != "FACTUAL_SUPPORTED":
        raise RuntimeError("Invalid generated category")
    if not isinstance(evidence_ids, list) or not evidence_ids or not set(evidence_ids).issubset(hit_by_id):
        raise RuntimeError("Invalid evidence IDs")
    evidence_sources = {hit_by_id[item]["source_id"] for item in evidence_ids}
    if source_id not in evidence_sources or source_id not in index["sources"]:
        raise RuntimeError("Invalid selected source")
    if not answer or sentence_count(answer) > 3 or re.search(r"https?://|www\.", answer, re.I):
        raise RuntimeError("Invalid answer format")
    if any(pattern.search(answer) for pattern in (*SENSITIVE_PATTERNS, *ADVICE_PATTERNS, *PERFORMANCE_PATTERNS)):
        raise RuntimeError("Generated answer contains prohibited content")
    evidence_text = "\n".join(hit_by_id[item]["text"] for item in evidence_ids)
    if not numbers(answer).issubset(numbers(evidence_text)):
        raise RuntimeError("Generated answer contains an unsupported numeric claim")
    selected_hit = next(hit_by_id[item] for item in evidence_ids if hit_by_id[item]["source_id"] == source_id)
    return response_payload(
        index,
        "FACTUAL_SUPPORTED",
        answer,
        source_id=source_id,
        evidence_ids=evidence_ids,
        source_updated_at=selected_hit["retrieved_at"],
    )


def answer_question(raw_question: Any) -> tuple[int, dict[str, Any]]:
    index = load_index()
    if not isinstance(raw_question, str):
        return 400, {"error": "question must be a string"}
    question = " ".join(raw_question.split())
    if not question:
        return 400, {"error": "Enter a question before submitting."}
    if len(question) > MAX_QUESTION_CHARACTERS:
        return 400, {"error": f"Keep the question within {MAX_QUESTION_CHARACTERS} characters."}

    category = classify(question)
    if category != "FACTUAL_CANDIDATE":
        return 200, response_payload(index, category, TEMPLATES[category])

    scheme_id, candidates = resolve_scheme(question)
    fact_type = resolve_fact_type(question)
    if len(candidates) > 1 or (fact_type in SCHEME_REQUIRED_FACTS and not scheme_id):
        return 200, response_payload(
            index,
            "CLARIFICATION_REQUIRED",
            TEMPLATES["CLARIFICATION_REQUIRED"],
            scheme_id=scheme_id,
        )
    if fact_type == "statement_process":
        return 200, response_payload(
            index,
            "UNSUPPORTED_BY_SOURCES",
            TEMPLATES["UNSUPPORTED_BY_SOURCES"],
            scheme_id=scheme_id,
        )
    try:
        hits = retrieve(question, index, scheme_id, fact_type)
        if not hits:
            return 200, response_payload(
                index,
                "UNSUPPORTED_BY_SOURCES",
                TEMPLATES["UNSUPPORTED_BY_SOURCES"],
                scheme_id=scheme_id,
            )
        return 200, generate(question, scheme_id, fact_type, hits, index)
    except Exception:
        return 503, response_payload(
            index,
            "SERVICE_ERROR",
            TEMPLATES["SERVICE_ERROR"],
            scheme_id=scheme_id,
        )


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        index = load_index()
        self._send_json(
            200,
            {
                "status": "ok",
                "embedding_model": index["embedding_model"],
                "chunk_count": len(index["records"]),
            },
        )

    def do_POST(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 20_000:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(content_length))
            status, response = answer_question(payload.get("question"))
            self._send_json(status, response)
        except (ValueError, json.JSONDecodeError, AttributeError):
            self._send_json(400, {"error": "Invalid JSON request."})
