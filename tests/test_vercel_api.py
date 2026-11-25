import api.query as vercel_api
import pytest


def test_exported_vercel_index_is_complete():
    index = vercel_api.load_index()

    assert index["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert index["embedding_dimension"] == 384
    assert len(index["records"]) == 59
    assert set(index["sources"]) == {"SRC-01", "SRC-02", "SRC-03", "SRC-04", "SRC-05"}


def test_vercel_api_short_circuits_sensitive_data(monkeypatch):
    monkeypatch.setattr(
        vercel_api,
        "query_embedding",
        lambda *_: (_ for _ in ()).throw(AssertionError("embedding must not run")),
    )

    status, response = vercel_api.answer_question("My PAN is ABCDE1234F")

    assert status == 200
    assert response["category"] == "SENSITIVE_DATA"
    assert response["citation"]["source_id"] == "SRC-01"


def test_vercel_api_requests_scheme_clarification_without_embedding(monkeypatch):
    monkeypatch.setattr(
        vercel_api,
        "query_embedding",
        lambda *_: (_ for _ in ()).throw(AssertionError("embedding must not run")),
    )

    status, response = vercel_api.answer_question("What is the expense ratio?")

    assert status == 200
    assert response["category"] == "CLARIFICATION_REQUIRED"


def test_vercel_api_retrieves_exported_scheme_fact(monkeypatch):
    index = vercel_api.load_index()
    expected = next(
        record
        for record in index["records"]
        if record["source_id"] == "SRC-02" and record["fact_type"] == "expense_ratio"
    )
    monkeypatch.setattr(vercel_api, "query_embedding", lambda *_: expected["embedding"])

    hits = vercel_api.retrieve(
        "Expense ratio for HDFC Large Cap",
        index,
        "hdfc_large_cap_direct_growth",
        "expense_ratio",
    )

    assert hits
    assert hits[0]["chunk_id"] == expected["chunk_id"]
    assert hits[0]["source_id"] == "SRC-02"


@pytest.mark.parametrize(
    ("question", "expected_answer", "source_id"),
    [
        (
            "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
            "HDFC Large Cap Fund Direct Growth — Expense ratio: 0.99%",
            "SRC-02",
        ),
        (
            "What is the lock-in period of HDFC ELSS Tax Saver Fund?",
            "HDFC ELSS Tax Saver Fund Direct Plan Growth — ELSS lock-in period: 3 years",
            "SRC-04",
        ),
        (
            "What is the exit load of HDFC Mid Cap Fund?",
            "HDFC Mid Cap Fund Direct Growth — Exit load of 1% if redeemed within 1 year.",
            "SRC-05",
        ),
    ],
)
def test_vercel_api_answers_single_verified_fact_when_inference_is_unavailable(
    monkeypatch, question, expected_answer, source_id
):
    monkeypatch.setattr(
        vercel_api,
        "query_embedding",
        lambda *_: (_ for _ in ()).throw(RuntimeError("inference unavailable")),
    )
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    status, response = vercel_api.answer_question(question)

    assert status == 200
    assert response["category"] == "FACTUAL_SUPPORTED"
    assert response["answer"] == expected_answer
    assert response["citation"]["source_id"] == source_id
    assert len(response["evidence_chunk_ids"]) == 1


def test_vercel_api_searches_approved_text_when_embeddings_are_unavailable(monkeypatch):
    monkeypatch.setattr(
        vercel_api,
        "query_embedding",
        lambda *_: (_ for _ in ()).throw(RuntimeError("inference unavailable")),
    )

    hits = vercel_api.retrieve(
        "What is the expense ratio of HDFC Large Cap Fund Direct Growth?",
        vercel_api.load_index(),
        "hdfc_large_cap_direct_growth",
        "expense_ratio",
    )

    assert [hit["source_id"] for hit in hits] == ["SRC-02"]
    assert hits[0]["fact_type"] == "expense_ratio"


def test_vercel_api_does_not_invent_a_direct_fact_for_an_unknown_field(monkeypatch):
    monkeypatch.setattr(
        vercel_api,
        "query_embedding",
        lambda *_: (_ for _ in ()).throw(RuntimeError("inference unavailable")),
    )

    status, response = vercel_api.answer_question(
        "Who manages HDFC Large Cap Fund Direct Growth?"
    )

    assert status == 200
    assert response["category"] == "UNSUPPORTED_BY_SOURCES"
    assert response["evidence_chunk_ids"] == []
