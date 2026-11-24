import api.query as vercel_api


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
